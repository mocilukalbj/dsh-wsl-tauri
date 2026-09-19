"""Optional Linux WebKitGTK regression test; no real Harness account is used.

Requires Python GI bindings for Gtk 3 and WebKit2 4.1. Verifies cold login,
reload, and a new process using persisted HttpOnly/SameSite=Strict cookies.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == '/?token=local-test':
            self.send_response(303)
            self.send_header('Set-Cookie', 'auth=local-test; Max-Age=3600; Path=/; HttpOnly; SameSite=Strict')
            self.send_header('Location', '/')
            self.end_headers()
            return
        valid = 'auth=local-test' in self.headers.get('Cookie', '').split('; ')
        self.send_response(200 if valid else 401)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<script>window.__DSH_BOOT__={};</script>Ready' if valid else b'Unauthorized')


def probe(port, directory, persisted):
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('WebKit2', '4.1')
    from gi.repository import Gtk, WebKit2, GLib

    manager = WebKit2.WebsiteDataManager(base_data_directory=directory, base_cache_directory=directory)
    context = WebKit2.WebContext.new_with_website_data_manager(manager)
    context.get_cookie_manager().set_persistent_storage(str(Path(directory) / 'cookies.db'), WebKit2.CookiePersistentStorage.SQLITE)
    splash = WebKit2.WebView.new_with_context(context)
    splash_window = Gtk.OffscreenWindow()
    splash_window.add(splash)
    splash_window.show_all()
    references = []
    outcomes = []

    def inspected(view, result):
        try:
            ok = view.run_javascript_finish(result).get_js_value().to_boolean()
        except Exception:
            ok = False
        outcomes.append(ok)
        print(('persisted' if persisted else 'cold'), 'load' if len(outcomes) == 1 else 'reload', 'OK' if ok else 'FAILED', flush=True)
        if ok and len(outcomes) == 1:
            view.reload()
        else:
            Gtk.main_quit()

    def loaded(view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            view.run_javascript('!!window.__DSH_BOOT__', None, inspected)

    def splash_loaded(view, event):
        if event != WebKit2.LoadEvent.FINISHED or references:
            return
        # Same WebsiteDataManager, but no tauri/file document in the main view.
        main = WebKit2.WebView.new_with_context(context)
        window = Gtk.OffscreenWindow()
        window.add(main)
        window.show_all()
        references.extend([main, window])
        main.connect('load-changed', loaded)
        suffix = '/' if persisted else '/?token=local-test'
        main.load_uri(f'http://127.0.0.1:{port}{suffix}')

    splash.connect('load-changed', splash_loaded)
    splash.load_html('<html>Connecting</html>', 'tauri://localhost')
    GLib.timeout_add_seconds(20, lambda: (Gtk.main_quit(), False)[1])
    Gtk.main()
    if references:
        references[1].destroy()
    splash_window.destroy()
    return 0 if outcomes == [True, True] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=int)
    parser.add_argument('--directory')
    parser.add_argument('--persisted', action='store_true')
    args = parser.parse_args()
    if args.probe:
        return probe(args.probe, args.directory, args.persisted)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Backend)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='dsh-auth-test-') as directory:
            command = [sys.executable, __file__, '--probe', str(server.server_port), '--directory', directory]
            subprocess.run(command, check=True, timeout=30)
            subprocess.run(command + ['--persisted'], check=True, timeout=30)
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
