#!/usr/bin/env python3
"""Compare candidate offline Android PDFs with synthetic LibreOffice goldens.

Fail closed on loss of text, images, pages or substantial visual differences.
A passing comparison DOES NOT certify device provenance or airplane mode.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from office_fidelity_probe import audit,pdf_structure
from offline_reference_suite import SPECS,sha256

MAX_MEAN_PIXEL_DIFF=0.055
MIN_WORD_OVERLAP=0.94

def inspect_case(spec,root:Path,candidate:Path,*,max_mean_diff:float=MAX_MEAN_PIXEL_DIFF)->dict:
    src=root/'synthetic_docx'/f'{spec.name}.docx'
    golden=root/'reference_pdf'/f'{spec.name}.pdf'
    output=candidate/f'{spec.name}.pdf'
    blockers=[]
    if not src.is_file() or not golden.is_file():
        return {'case':spec.name,'result':'FAIL','blockers':['REFERENCE_FILES_MISSING']}
    if not output.is_file():
        return {'case':spec.name,'result':'FAIL','blockers':['ANDROID_PDF_MISSING']}
    try:
        summary=audit(src,output,golden)
        observed=pdf_structure(output)
        reference=pdf_structure(golden)
        if summary['hard_failures']:blockers.extend(summary['hard_failures'])
        if summary['word_overlap']<MIN_WORD_OVERLAP:
            blockers.append('WORD_OVERLAP_BELOW_FIDELITY_GATE')
        if observed['pages']!=reference['pages']:
            blockers.append('PAGE_COUNT_DIFFERENCE')
        if observed['embedded_images']<reference['embedded_images']:
            blockers.append('EMBEDDED_IMAGES_LOST')
        visual=summary['visual']
        if visual['status']!='MEASURED_NOT_PASS':
            blockers.append('VISUAL_COMPARISON_UNAVAILABLE')
        else:
            for p in visual['pages']:
                diff=p.get('mean_absolute_pixel_difference')
                if diff is None or diff>max_mean_diff:
                    blockers.append(f'VISUAL_PAGE_{p["page"]}_DIFFERENCE_OR_SKIPPED')
    except Exception as exc:
        return {'case':spec.name,'result':'FAIL',
                'blockers':['UNREADABLE_OR_INVALID_PDF:'+type(exc).__name__]}
    return {'case':spec.name,
            'result':'CANDIDATE_STATIC_PASS' if not blockers else 'FAIL',
            'blockers':sorted(set(blockers)),'candidate_sha256':sha256(output),
            'word_overlap':summary['word_overlap'],'visual':summary['visual'],
            'real_android_device_tested':False,'airplane_mode_proved':False}

def compare(root:Path,candidate:Path,*,max_mean_diff:float=MAX_MEAN_PIXEL_DIFF)->dict:
    if not 0<=max_mean_diff<=0.20:raise ValueError('INVALID_VISUAL_DIFF_LIMIT')
    root=Path(root).resolve();candidate=Path(candidate).resolve()
    path=root/'suite-report.json'
    if not path.is_file():raise ValueError('REFERENCE_SUITE_REPORT_MISSING')
    report=json.loads(path.read_text(encoding='utf-8'))
    if (report.get('schema_version')!=1 or report.get('status')!='REFERENCE_PASS'
            or len(report.get('cases',[]))!=len(SPECS)
            or any(row.get('result')!='REFERENCE_PASS' for row in report['cases'])
            or {row.get('case') for row in report['cases']}!={x.name for x in SPECS}):
        raise ValueError('REFERENCE_NOT_QUALIFIED')
    results=[]
    for spec in SPECS:
        row=next(x for x in report['cases'] if x['case']==spec.name)
        src=root/'synthetic_docx'/f'{spec.name}.docx'
        golden=root/'reference_pdf'/f'{spec.name}.pdf'
        if not src.is_file() or not golden.is_file():
            raise ValueError('REFERENCE_FILES_MISSING')
        if sha256(src)!=row['docx_sha256'] or sha256(golden)!=row['pdf_sha256']:
            raise ValueError('REFERENCE_SHA256_MISMATCH')
        results.append(inspect_case(spec,root,candidate,max_mean_diff=max_mean_diff))
    return {'status':'CANDIDATE_STATIC_PASS' if all(x['result']=='CANDIDATE_STATIC_PASS' for x in results) else 'FAIL',
            'cases':results,'device_provenance_verified':False,
            'airplane_mode_verified':False,'native_office_in_formatlab_proved':False,
            'release_authorized':False}

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',type=Path,required=True)
    p.add_argument('--candidate-dir',type=Path,required=True)
    p.add_argument('--max-mean-diff',type=float,default=MAX_MEAN_PIXEL_DIFF)
    p.add_argument('--report',type=Path)
    args=p.parse_args(argv)
    try:result=compare(args.suite,args.candidate_dir,max_mean_diff=args.max_mean_diff)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('ANDROID_FIDELITY_GATE_BLOCKED:',str(exc),file=sys.stderr)
        return 3
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(text,encoding='utf-8')
    print(json.dumps({'status':result['status'],'failures':[
        (x['case'],x['blockers']) for x in result['cases'] if x['blockers']]},ensure_ascii=False))
    return 0 if result['status']=='CANDIDATE_STATIC_PASS' else 2

if __name__=='__main__':raise SystemExit(main())
