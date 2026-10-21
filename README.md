# FormatLab Android — offline builds

## Jelenlegi mérföldkő

- **v0.2.1:** lefordított és telefonon igazolt debug APK (képkonvertálás, ZIP, fájlmentés, e-mail-megosztás, CSV→JSON). [Bizonyítottan működő v0.2.1 APK](https://github.com/misssska/formatlab-android-public-build/releases/tag/formatlab-debug-v0.2.1-run-3)
- **v0.3.0:** a helyben ellenőrzött forráscsomag elkészült, de **APK-fordítás és valódi telefonos teszt még nem történt**.
- Az eredeti `misssska/formatlab-android-` repository **privát, változatlan**.

## Android v0.3 fordítása telefonról, számítógép nélkül

1. A ChatGPT-beszélgetésben töltsd le: `FormatLab-Android-v0.3-offline-source.zip`; ne csomagold ki.
2. Nyisd meg a [GitHub feltöltőt](https://github.com/misssska/formatlab-android-public-build/upload/main).
3. A ZIP-et a repository **gyökerébe** töltsd fel, változatlan néven, majd `Commit changes` a main ágra.
4. A `FormatLab Android v0.3 offline debug APK` [GitHub Actions](https://github.com/misssska/formatlab-android-public-build/actions) automatikusan elindul.
5. Sikeres fordítás után [GitHub Releases](https://github.com/misssska/formatlab-android-public-build/releases) oldalon lesz a `FormatLab-Android-v0.3-debug.apk`.

Az engedélyezett forrás ZIP SHA-256 ellenőrzőösszege:

```text
04694a0afbc26ebcbe7dd0c4c265d656acc05497d6d5765980c22e4366c0123b
```

A workflow nem használ külső feldolgozószervert; csak **a fejlesztői APK fordítása** történik GitHubon. A telefonon a konvertálás internet nélkül fut.

## v0.3 offline funkciók (fejlesztői, még készülékes tesztet igényel)

- PDF első oldal → PNG/JPG, PDF összes oldala → PNG/JPG ZIP-ben (max. 20 oldal)
- TXT/CSV/JSON/MD → PDF/DOCX; DOCX → TXT/PDF szövegkinyeréssel
- Képek → BMP, TIFF, ICO, valamint valódi kontúr- vagy plotteres SVG
- Képek → PDF, MP4 AAC hang → M4A, fájlelőnézet
- A v0.2.1 összes korábban tesztelt funkciójának megőrzése

**Korlátok:** nincs régi DOC/XLS import, professzionális PDF↔Word formázáshűség, OCR vagy általános videóátkódolás. AVIF/HEIC csak támogatott Android-rendszerdekóderrel. A forrás nyilvánosan olvasható; titkos kulcsot ne tölts fel.

## Biztonság

- Az Android manifest nem tartalmaz INTERNET vagy tárhely-hozzáférési jogosultságot.
- A natív dokumentummotor méret-, pixel-, oldalszám- és XML-korlátokkal működik.
- A GitHub Actions SHA-256 ellenőrzött forrásból dolgozik, majd debug APK-t publikál release assetként, megkerülve a betelt Actions-artifact kvótát.
