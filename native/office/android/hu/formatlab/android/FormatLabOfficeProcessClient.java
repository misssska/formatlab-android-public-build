package hu.formatlab.android;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.os.Messenger;
import android.os.RemoteException;
import java.io.File;
import java.io.IOException;

/**
 * Application-side binder client for a single offline DOCX->PDF request.
 * UI wiring is deferred until a real native engine/device quality acceptance.
 */
public final class FormatLabOfficeProcessClient implements AutoCloseable {
    public interface Callback {
        void onCompleted(File privatePdf);
        void onError(String status);
    }

    private final Context context;
    private final Uri source;
    private final Callback callback;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Messenger inbound = new Messenger(new Handler(Looper.getMainLooper(),
            this::onWorkerMessage));
    private boolean bound = false;
    private boolean finished = false;

    private final ServiceConnection connection = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            if (finished) return;
            Message request = Message.obtain(null, FormatLabOfficeService.COMMAND_CONVERT);
            Bundle data = new Bundle();
            data.putParcelable(FormatLabOfficeService.KEY_SOURCE, source);
            request.setData(data);
            request.replyTo = inbound;
            try {
                new Messenger(binder).send(request);
            } catch (RemoteException ex) {
                fail("OFFICE_IPC_ERROR");
            }
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            fail("OFFICE_WORKER_PROCESS_LOST");
        }
        @Override public void onBindingDied(ComponentName name) {
            fail("OFFICE_WORKER_BINDING_DIED");
        }
        @Override public void onNullBinding(ComponentName name) {
            fail("OFFICE_WORKER_BINDING_NULL");
        }
    };

    public FormatLabOfficeProcessClient(Context context, Uri source, Callback callback) {
        this.context = context.getApplicationContext();
        this.source = source;
        this.callback = callback;
    }

    /** Must be invoked on UI thread, from a foreground user action. */
    public void start() {
        if (Looper.myLooper() != Looper.getMainLooper())
            throw new IllegalStateException("Bind must start on main thread");
        if (finished || bound || source == null || !"content".equals(source.getScheme())) {
            fail("BAD_INPUT");
            return;
        }
        Intent intent = new Intent(context, FormatLabOfficeService.class);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.setData(source);
        bound = context.bindService(intent, connection, Context.BIND_AUTO_CREATE);
        if (!bound) fail("OFFICE_BIND_FAILED");
    }

    private boolean onWorkerMessage(Message response) {
        if (finished) return true;
        Bundle data = response.getData();
        if (response.what == FormatLabOfficeService.RESULT_OK) {
            String path = data.getString(FormatLabOfficeService.KEY_OUTPUT);
            try {
                File file = path == null ? null : new File(path).getCanonicalFile();
                File cache = new File(context.getCacheDir(), "formatlab-office").getCanonicalFile();
                if (file == null || !cache.equals(file.getParentFile())
                        || !file.getName().startsWith("office-out-")
                        || !file.getName().endsWith(".pdf") || !file.isFile()) {
                    fail("OFFICE_OUTPUT_PATH_INVALID");
                    return true;
                }
                finish();
                callback.onCompleted(file);
            } catch (IOException ex) {
                fail("OFFICE_OUTPUT_PATH_INVALID");
            }
        } else {
            fail(data.getString(FormatLabOfficeService.KEY_STATUS,"OFFICE_ERROR"));
        }
        return true;
    }

    private void fail(String reason) {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            main.post(() -> fail(reason));
            return;
        }
        if (finished) return;
        finish();
        callback.onError(reason);
    }

    private void finish() {
        if (finished) return;
        finished = true;
        if (bound) {
            context.unbindService(connection);
            bound = false;
        }
    }

    @Override public void close() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            main.post(this::close);
        } else {
            finish();
        }
    }
}
