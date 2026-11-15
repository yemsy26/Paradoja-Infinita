"""FFmpeg: video crudo por pipe + mezcla de audio + subtitulos -> MP4 con NVENC."""
import queue
import subprocess
import threading
from pathlib import Path

from .config import VideoSpec


def _works(codec: str) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
         "-frames:v", "1", "-c:v", codec, "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


def pick_codec(requested: str) -> str:
    if requested != "auto":
        return requested
    return "h264_nvenc" if _works("h264_nvenc") else "libx264"


_VIDEO_ARGS = {
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "22",
                   "-b:v", "10M", "-maxrate", "16M", "-bufsize", "20M", "-spatial-aq", "1",
                   "-temporal-aq", "1", "-bf", "2", "-profile:v", "high"],
    "hevc_nvenc": ["-c:v", "hevc_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "24",
                   "-b:v", "8M", "-maxrate", "14M", "-bufsize", "16M", "-spatial-aq", "1",
                   "-tag:v", "hvc1"],
    "libx264": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high"],
}


class FfmpegEncoder:
    def __init__(self, spec: VideoSpec, codec: str, clips: list, bed: Path, ass_name: str,
                 out: Path, workdir: Path):
        n = len(clips)
        fc = [f"[0:v]ass={ass_name}[v]"]
        labels = ""
        for i, c in enumerate(clips, start=1):
            ms = round(c.start * 1000)
            fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=1.6,"
                      f"adelay={ms}|{ms}[a{i}]")
            labels += f"[a{i}]"
        fc.append(f"[{n + 1}:a]aformat=sample_rates=48000:channel_layouts=stereo[bed]")
        fc.append(f"{labels}[bed]amix=inputs={n + 1}:normalize=0:duration=longest,alimiter=limit=0.95[aout]")

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{spec.width}x{spec.height}",
               "-framerate", str(spec.fps), "-i", "pipe:0"]
        for c in clips:
            cmd += ["-i", str(c.path.resolve())]
        cmd += ["-i", str(bed.resolve()),
                "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[aout]",
                *_VIDEO_ARGS[codec], "-pix_fmt", "yuv420p", "-g", str(spec.fps * 2),
                "-r", str(spec.fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-t", f"{spec.duration:.3f}", "-movflags", "+faststart", str(out.resolve())]

        self.log = (workdir / "ffmpeg.log").open("wb")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self.log, cwd=workdir)
        self.q = queue.Queue(maxsize=8)
        self.error = None
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self):
        while (item := self.q.get()) is not None:
            try:
                self.proc.stdin.write(item)
            except OSError as e:
                self.error = e
                return

    def write(self, data: bytes):
        while True:
            if self.error:
                raise RuntimeError(f"ffmpeg cerro el pipe (ver ffmpeg.log): {self.error}")
            try:
                self.q.put(data, timeout=0.5)
                return
            except queue.Full:
                pass

    def close(self) -> int:
        if not self.error:
            self.q.put(None)
            self.thread.join()
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        rc = self.proc.wait()
        self.log.close()
        return rc
