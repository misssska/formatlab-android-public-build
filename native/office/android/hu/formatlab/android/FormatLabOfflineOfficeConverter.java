package hu.formatlab.android;

// FormatLab offline LibreOfficeKit adapter (candidate, NOT wired into the user UI).
// It requires the real pinned native engine AND its bootstrap/registry/fonts in APK.
// Copyright (c) FormatLab contributors. No online fallback.
import android.app.Activity;
import android.content.res.AssetManager;
import android.net.Uri;
import android.os.Looper;
import android.util.Log;

import org.libreoffice.kit.Document;
import org.libreoffice.kit.LibreOfficeKit;
import org.libreoffice.kit.Office;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.security.SecureRandom;
import java.util.Locale;

/**
 * A narrow, strictly offline DOCX -> PDF integration candidate.
 *
 * It does NOT ship LibreOffice, does NOT claim document fidelity, and must not be
 * attached to the public FormatLab UI before the native package/device gates pass.
 *
 * Run from a dedicated background worker / isolated process. A thread interrupt
 * cannot reliably cancel native LibreOffice calls; process isolation is mandatory
 * before untrusted document conversion is offered as a public feature.
 */
public final class FormatLabOfflineOfficeConverter {
    public static final long MAX_DOCX_BYTES = 40L * 1024L * 1024L;
    public static final long MAX_PDF_BYTES = 100L * 1024L * 1024L;
    public static final String INPUT_EXTENSION = ".docx";
    public static final String OUTPUT_EXTENSION = ".pdf";

    private static final String TAG = "FormatLabOffice";
    private static final Object NATIVE_LOCK = new Object();
    private static Office sharedOffice = null;
    private static final SecureRandom RANDOM = new SecureRandom();

    private FormatLabOfflineOfficeConverter() {}

    public enum Status {
        ENGINE_NOT_PACKAGED, BAD_INPUT, DOCUMENT_LOAD_FAILED,
        CONVERSION_FAILED, OUTPUT_INVALID, NATIVE_ENGINE_ERROR
    }

    public static final class ConversionException extends IOException {
        public final Status status;
        public ConversionException(Status status, String message) {
            super(message);
            this.status = status;
        }
        public ConversionException(Status status, String message, Throwable cause) {
            super(message, cause);
            this.status = status;
        }
    }

    /** All native dependencies and assets must be packaged before any JNI call. */
    public static boolean isEnginePackaged(Activity activity) {
        if (activity == null) return false;
        File nativeDir = new File(activity.getApplicationInfo().nativeLibraryDir);
        if (!new File(nativeDir, "liblo-native-code.so").isFile()) return false;
        AssetManager assets = activity.getAssets();
        String[] requiredAssets = {
                "program/fundamentalrc",
                "program/bootstraprc",
                "program/unorc",
                "program/versionrc",
                "share/registry/main.xcd",
                "share/registry/res/registry_en-US.xcd",
                "unpack/program/sofficerc"
        };
        for (String name : requiredAssets) {
            try (InputStream ignored = assets.open(name)) {
                // existence verified; no asset contents logged
            } catch (IOException error) {
                return false;
            }
        }
        try {
            String[] fonts = assets.list("unpack/user/fonts");
            if (fonts == null) return false;
            for (String font : fonts) {
                String lower = font.toLowerCase(Locale.ROOT);
                if (lower.endsWith(".ttf") || lower.endsWith(".otf")) return true;
            }
        } catch (IOException ignored) {
            return false;
        }
        return false;
    }

    /**
     * Copies content from a Storage Access Framework Uri to a private temporary file.
     * The output remains in private cache until the caller explicitly saves/shares it.
     * This method must not run on the main thread.
     */
    public static File convertDocxToPrivatePdf(Activity activity, Uri source)
            throws ConversionException {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            throw new ConversionException(Status.CONVERSION_FAILED,
                    "Office conversion must run on a background thread");
        }
        if (activity == null || source == null) {
            throw new ConversionException(Status.BAD_INPUT, "Missing document");
        }
        if (!isEnginePackaged(activity)) {
            throw new ConversionException(Status.ENGINE_NOT_PACKAGED,
                    "LibreOffice native engine or bootstrap assets unavailable");
        }
        synchronized (NATIVE_LOCK) {
            File inputFile = null;
            File outputFile = null;
            boolean success = false;
            try {
                File workDir = new File(activity.getCacheDir(), "formatlab-office");
                if (!workDir.isDirectory() && !workDir.mkdirs()) {
                    throw new IOException("Cannot allocate private office directory");
                }
                inputFile = File.createTempFile("office-in-", INPUT_EXTENSION, workDir);
                outputFile = File.createTempFile("office-out-", OUTPUT_EXTENSION, workDir);
                // Delete an empty placeholder: native saveAs creates the output itself.
                if (!outputFile.delete()) throw new IOException("Cannot prepare PDF destination");

                copyBoundedDocx(activity, source, inputFile);

                Office office = prepareNativeOffice(activity);
                Document doc = null;
                try {
                    doc = office.documentLoad(Uri.fromFile(inputFile).toString());
                    if (doc == null) {
                        throw new ConversionException(Status.DOCUMENT_LOAD_FAILED,
                                "LibreOffice could not open DOCX");
                    }
                    doc.saveAs(Uri.fromFile(outputFile).toString(), "pdf", "");
                } finally {
                    if (doc != null) {
                        try { doc.destroy(); }
                        catch (RuntimeException ex) { Log.w(TAG, "Document cleanup failed"); }
                    }
                }

                verifyPdf(outputFile);
                success = true;
                return outputFile;
            } catch (ConversionException ex) {
                throw ex;
            } catch (LinkageError ex) {
                throw new ConversionException(Status.NATIVE_ENGINE_ERROR,
                        "Native engine entry points unavailable", ex);
            } catch (IOException | RuntimeException ex) {
                throw new ConversionException(Status.CONVERSION_FAILED,
                        "Local Office conversion failed", ex);
            } finally {
                if (inputFile != null) inputFile.delete();
                if (!success && outputFile != null) outputFile.delete();
            }
        }
    }

    private static Office prepareNativeOffice(Activity activity) throws ConversionException {
        if (sharedOffice != null) return sharedOffice;
        try {
            LibreOfficeKit.init(activity);
            ByteBuffer handle = LibreOfficeKit.getLibreOfficeKitHandle();
            if (handle == null || !handle.isDirect()) {
                throw new ConversionException(Status.NATIVE_ENGINE_ERROR,
                        "LibreOfficeKit did not return a native handle");
            }
            sharedOffice = new Office(handle);
            return sharedOffice;
        } catch (LinkageError ex) {
            throw new ConversionException(Status.NATIVE_ENGINE_ERROR,
                    "Native LibreOfficeKit cannot initialize", ex);
        }
    }

    private static void copyBoundedDocx(Activity activity, Uri uri, File destination)
            throws IOException {
        long count = 0;
        try (InputStream in = activity.getContentResolver().openInputStream(uri);
             FileOutputStream out = new FileOutputStream(destination)) {
            if (in == null) throw new ConversionException(Status.BAD_INPUT, "Document unavailable");
            byte[] bytes = new byte[64 * 1024];
            int len;
            while ((len = in.read(bytes)) != -1) {
                count += len;
                if (count > MAX_DOCX_BYTES) {
                    throw new ConversionException(Status.BAD_INPUT, "DOCX exceeds size limit");
                }
                if (Thread.currentThread().isInterrupted()) {
                    throw new ConversionException(Status.CONVERSION_FAILED,
                            "Conversion interrupted before native execution");
                }
                out.write(bytes, 0, len);
            }
        }
        if (count < 8) throw new ConversionException(Status.BAD_INPUT, "DOCX is empty or truncated");
        try (FileInputStream in = new FileInputStream(destination)) {
            int a = in.read(), b = in.read();
            if (a != 'P' || b != 'K') {
                throw new ConversionException(Status.BAD_INPUT, "Input is not a ZIP-based DOCX");
            }
        }
    }

    private static void verifyPdf(File file) throws IOException {
        if (!file.isFile() || file.length() < 100 || file.length() > MAX_PDF_BYTES) {
            throw new ConversionException(Status.OUTPUT_INVALID,
                    "PDF missing or outside size limits");
        }
        try (FileInputStream in = new FileInputStream(file)) {
            byte[] header = new byte[5];
            if (in.read(header) != 5
                    || header[0] != '%' || header[1] != 'P' || header[2] != 'D'
                    || header[3] != 'F' || header[4] != '-') {
                throw new ConversionException(Status.OUTPUT_INVALID, "Output is not a PDF");
            }
        }
    }

    /** Caller is responsible for copying an accepted output through SAF and deleting it. */
    public static void cleanupPrivateOutput(File file, Activity activity) {
        if (file == null || activity == null) return;
        try {
            File canonicalRoot = new File(activity.getCacheDir(), "formatlab-office")
                    .getCanonicalFile();
            File canonical = file.getCanonicalFile();
            if (canonical.getParentFile().equals(canonicalRoot)
                    && canonical.getName().startsWith("office-out-")
                    && canonical.getName().endsWith(OUTPUT_EXTENSION)) {
                canonical.delete();
            }
        } catch (IOException ignored) {
            Log.w(TAG, "Failed to validate private output cleanup path");
        }
    }
}
