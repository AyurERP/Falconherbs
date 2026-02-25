"""
Video Creator — Slideshow videos from images using moviepy.
FREE — no external API. Used for Instagram Reels, product promos.
"""

from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class VideoCreator:
    """Creates slideshow videos from images. No API cost."""

    def __init__(self, brand_guidelines: Optional[dict] = None):
        self.brand = brand_guidelines or {}

    def create_slideshow(
        self,
        image_paths: List[Path],
        output_path: Path,
        duration_per_image: float = 3.0,
        transition: str = "crossfade",
        music_path: Optional[Path] = None,
        size: Tuple[int, int] = (1080, 1920),
    ) -> dict:
        """
        Create video from images using moviepy.
        Each image shown for duration_per_image seconds.
        """
        if not image_paths:
            return {"success": False, "error": "No images provided"}

        try:
            from moviepy.editor import (
                ImageSequenceClip,
                concatenate_videoclips,
                CompositeVideoClip,
            )
            from PIL import Image
        except ImportError as e:
            return {
                "success": False,
                "error": f"moviepy or Pillow not installed: {e}. Run: pip install moviepy Pillow",
            }

        try:
            # Resize images to target size
            resized_dir = output_path.parent / "_temp_resized"
            resized_dir.mkdir(parents=True, exist_ok=True)
            resized_paths = []

            for i, img_path in enumerate(image_paths):
                img = Image.open(img_path).convert("RGB")
                img = img.resize(size, Image.Resampling.LANCZOS)
                out = resized_dir / f"frame_{i:03d}.jpg"
                img.save(out, "JPEG", quality=90)
                resized_paths.append(str(out))

            # Create clip from images (each image shown for duration_per_image seconds)
            durations = [duration_per_image] * len(resized_paths)
            clip = ImageSequenceClip(resized_paths, durations=durations)


            # Add music if provided
            if music_path and music_path.exists():
                try:
                    from moviepy.editor import AudioFileClip
                    audio = AudioFileClip(str(music_path))
                    # Trim audio to video length
                    if audio.duration > clip.duration:
                        audio = audio.subclip(0, clip.duration)
                    clip = clip.set_audio(audio)
                except Exception as e:
                    pass  # Continue without music

            clip.write_videofile(
                str(output_path),
                fps=24,
                codec="libx264",
                audio_codec="aac" if (music_path and music_path.exists()) else None,
                preset="medium",
                verbose=False,
                logger=None,
            )
            clip.close()

            # Cleanup temp
            for p in resized_paths:
                try:
                    Path(p).unlink()
                except Exception:
                    pass
            try:
                resized_dir.rmdir()
            except Exception:
                pass

            return {
                "success": True,
                "filepath": str(output_path),
                "message": f"🎬 Video created: {output_path.name}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_text_video(
        self,
        text_slides: List[str],
        output_path: Path,
        duration_per_slide: float = 4.0,
        background_color: Optional[str] = None,
        font_color: Optional[str] = None,
        size: Tuple[int, int] = (1080, 1920),
    ) -> dict:
        """Create text-based promo video (sale announcements, etc.)."""
        try:
            from moviepy.editor import ImageClip, TextClip, concatenate_videoclips
            from PIL import Image
            import numpy as np
        except ImportError as e:
            return {
                "success": False,
                "error": f"moviepy or Pillow not installed: {e}",
            }

        bg = background_color or self.brand.get("colors", {}).get("background", "#F5F0E8")
        fg = font_color or self.brand.get("colors", {}).get("text", "#1A1A1A")

        def rgb_from_hex(h: str) -> Tuple[int, int, int]:
            h = h.lstrip("#")
            return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

        bg_rgb = rgb_from_hex(bg)


        try:
            clips = []
            for text in text_slides:
                # Create solid color frame
                frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
                frame[:] = bg_rgb

                # Create PIL image with text
                img = Image.fromarray(frame)
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", 72)
                except Exception:
                    font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                x = (size[0] - tw) // 2
                y = (size[1] - th) // 2
                draw.text((x, y), text, fill=fg, font=font)

                tmp_path = output_path.parent / f"_slide_{len(clips)}.png"
                img.save(tmp_path)
                clip = ImageClip(str(tmp_path)).with_duration(duration_per_slide)
                clips.append(clip)
                tmp_path.unlink(missing_ok=True)

            final = concatenate_videoclips(clips)
            final.write_videofile(
                str(output_path),
                fps=24,
                codec="libx264",
                verbose=False,
                logger=None,
            )
            final.close()
            return {"success": True, "filepath": str(output_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}
