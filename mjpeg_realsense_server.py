#!/usr/bin/env python3
import argparse
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class Handler(BaseHTTPRequestHandler):
    cap = None
    fps = 15
    quality = 80

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = b"<html><body><h3>Robot MJPEG</h3><img src='/stream' style='max-width:100%;height:auto;'/></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path != "/stream":
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        period = 1.0 / max(1, self.fps)
        while True:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.02)
                continue
            ok, enc = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
            if not ok:
                continue
            jpg = enc.tobytes()
            try:
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
                time.sleep(period)
            except (BrokenPipeError, ConnectionResetError):
                break

    def log_message(self, format, *args):
        return


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="/dev/video2")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--fps", type=int, default=15)
    p.add_argument("--quality", type=int, default=80)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8091)
    args = p.parse_args()

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open camera: {args.device}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    Handler.cap = cap
    Handler.fps = args.fps
    Handler.quality = args.quality

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving on http://{args.host}:{args.port}/stream")
    try:
        server.serve_forever()
    finally:
        cap.release()
        server.server_close()


if __name__ == "__main__":
    main()
