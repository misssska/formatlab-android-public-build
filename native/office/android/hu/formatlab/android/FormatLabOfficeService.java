package hu.formatlab.android;

import android.app.Service;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.os.Messenger;
import android.os.Process;
import android.os.RemoteException;
import android.util.Log;
import java.io.File;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Not exported. Runs in dedicated :office process; native hangs/crashes cannot
 * execute inside the UI process. Not enabled in the existing v0.3 user interface.
 * Its fixed watchdog kills THIS process, not the app UI process.
 */
public final class FormatLabOfficeService extends Service {
    public static final int COMMAND_CONVERT = 1;
    public static final int RESULT_OK = 10;
    public static final int RESULT_ERROR = 11;
    public static final int MAX_SECONDS = 180;
    public static final String KEY_SOURCE = "source";
    public static final String KEY_OUTPUT = "output";
    public static final String KEY_STATUS = "status";
    private static final String TAG = "FormatLabOfficeService";

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final AtomicBoolean busy = new AtomicBoolean(false);
    private final Messenger messenger = new Messenger(new Handler(Looper.getMainLooper(),
            this::onClientMessage));

    @Override public IBinder onBind(Intent intent) { return messenger.getBinder(); }

    private boolean onClientMessage(Message request) {
        if (request.what != COMMAND_CONVERT || request.replyTo == null) return true;
        Messenger reply = request.replyTo;
        Bundle incoming = request.getData();
        Uri source = incoming == null ? null : incoming.getParcelable(KEY_SOURCE);
        if (source == null || !"content".equals(source.getScheme())) {
            send(reply, RESULT_ERROR, "BAD_INPUT", null);
            return true;
        }
        if (!busy.compareAndSet(false, true)) {
            send(reply, RESULT_ERROR, "OFFICE_BUSY", null);
            return true;
        }
        AtomicBoolean completed = new AtomicBoolean(false);
        Runnable watchdog = () -> {
            if (!completed.compareAndSet(false, true)) return;
            send(reply, RESULT_ERROR, "OFFICE_TIMEOUT", null);
            // Kill only the :office process. Thread interruption is insufficient
            // for arbitrary native LibreOffice calls that can deadlock.
            Process.killProcess(Process.myPid());
        };
        mainHandler.postDelayed(watchdog, MAX_SECONDS * 1000L);
        Thread worker = new Thread(() -> {
            File pdf = null;
            try {
                pdf = FormatLabOfflineOfficeConverter.convertDocxToPrivatePdf(this, source);
                if (completed.compareAndSet(false, true)) {
                    send(reply, RESULT_OK, "PDF_READY", pdf.getAbsolutePath());
                }
            } catch (FormatLabOfflineOfficeConverter.ConversionException ex) {
                if (completed.compareAndSet(false, true)) {
                    send(reply, RESULT_ERROR, ex.status.name(), null);
                }
            } catch (RuntimeException | LinkageError ex) {
                Log.e(TAG, "Native conversion worker failed", ex);
                if (completed.compareAndSet(false, true)) {
                    send(reply, RESULT_ERROR, "OFFICE_WORKER_FAILED", null);
                }
            } finally {
                mainHandler.removeCallbacks(watchdog);
                busy.set(false);
            }
        }, "formatlab-office-native-worker");
        worker.setDaemon(true);
        worker.start();
        return true;
    }

    private static void send(Messenger receiver, int code, String status, String output) {
        Message message = Message.obtain(null, code);
        Bundle extras = new Bundle();
        extras.putString(KEY_STATUS, status);
        if (output != null) extras.putString(KEY_OUTPUT, output);
        message.setData(extras);
        try { receiver.send(message); } catch (RemoteException ignored) {
            Log.w(TAG, "FormatLab UI receiver not available");
        }
    }
}
