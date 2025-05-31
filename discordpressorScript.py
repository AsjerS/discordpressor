import sys
import subprocess
import os
import json
import shutil


# Constants
MAX_SIZE_MB = 9
DEFAULT_VIDEO_BITRATE = 5_000_000
AUDIO_BITRATE = 128_000
MAX_HEIGHT_UNTIL_HALVE = 1440
ENCODING_PRESET = "slower" # Choose from: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow

FFPROBE_CMD = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,r_frame_rate:format=duration",
               "-of", "json"]


def get_video_info(filepath):
    cmd = FFPROBE_CMD + [filepath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        if not data.get('streams') or not data['streams']:
            print(f"Error: No video streams found in ffprobe output for {filepath}.")
            return None, None, None, None
        stream_info = data['streams'][0]

        width_raw = stream_info.get('width')
        height_raw = stream_info.get('height')
        
        if 'format' not in data or 'duration' not in data['format']:
            print(f"Error: Duration not found in ffprobe output format section for {filepath}.")
            return None, None, None, None
        duration_str = data['format'].get('duration')

        if width_raw is None or height_raw is None or duration_str is None:
            print(f"Error: Missing essential video info (W, H, or D) for {filepath}. "
                  f"W:{width_raw}, H:{height_raw}, D_str:{duration_str}")
            return None, None, None, None

        try:
            width = int(width_raw)
            height = int(height_raw)
            duration = float(duration_str)
            if duration <= 0:
                print(f"Error: Video duration ({duration}s) for {filepath} is not positive.")
                return None, None, None, None
        except ValueError as e:
            print(f"Error converting essential video info (W, H, D) to number for {filepath}: {e}")
            return None, None, None, None

        original_fps = None
        r_frame_rate_str = stream_info.get('r_frame_rate')
        if r_frame_rate_str:
            try:
                if '/' in r_frame_rate_str:
                    num_str, den_str = r_frame_rate_str.split('/')
                    num = float(num_str)
                    den = float(den_str)
                    if den != 0:
                        parsed_fps = num / den
                        if parsed_fps > 0:
                            original_fps = parsed_fps
                        else:
                            print(f"Warning: Parsed original FPS from '{r_frame_rate_str}' for {filepath} is not positive ({parsed_fps}). Framerate will not be changed.")
                    else:
                        print(f"Warning: Invalid r_frame_rate denominator '0' in '{r_frame_rate_str}' for {filepath}. Framerate will not be changed.")
                else:
                    parsed_fps = float(r_frame_rate_str)
                    if parsed_fps > 0:
                        original_fps = parsed_fps
                    else:
                        print(f"Warning: Parsed original FPS from '{r_frame_rate_str}' for {filepath} is not positive ({parsed_fps}). Framerate will not be changed.")
            except ValueError:
                print(f"Warning: Could not parse r_frame_rate '{r_frame_rate_str}' for {filepath}. Framerate will not be changed.")
        else:
            print(f"Warning: r_frame_rate not found in video stream info for {filepath}. Framerate will not be changed.")
        
        return width, height, duration, original_fps

    except FileNotFoundError:
        print("Error: ffprobe command not found. Please ensure ffprobe is installed and in your PATH.")
        return None, None, None, None
    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe for {filepath}: {e}")
        print(f"ffprobe stderr: {e.stderr.decode(errors='ignore')}")
        return None, None, None, None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from ffprobe for {filepath}: {e}")
        return None, None, None, None
    except (KeyError, IndexError) as e:
        print(f"Error parsing ffprobe JSON (KeyError/IndexError) for {filepath}: {e}")
        return None, None, None, None
    except Exception as e:
        print(f"An unexpected error occurred while getting video info for {filepath}: {e}")
        return None, None, None, None

def calculate_target_framerate(original_fps_val):
    if original_fps_val is None or original_fps_val <= 0:
        return None 

    target_fps = original_fps_val
    changed = False
    if original_fps_val > 100:
        target_fps = original_fps_val / 4.0
        changed = True
    elif original_fps_val > 50:
        target_fps = original_fps_val / 2.0
        changed = True
    
    return target_fps if changed else None

def calculate_target_bitrate(duration_sec, max_size_mb, audio_bitrate):
    max_bits = max_size_mb * 8 * 1024 * 1024
    if duration_sec <= 0:
        print("Warning: Video duration is zero or negative. Using default bitrate for calculation.")
        return DEFAULT_VIDEO_BITRATE 
    video_bitrate_target = (max_bits / duration_sec) - audio_bitrate
    return max(100_000, int(video_bitrate_target))

def convert_video(input_path):
    if not os.path.isfile(input_path):
        print(f"File not found: {input_path}")
        return

    base, _ = os.path.splitext(input_path)
    temp_output = f"{base}_temp.mp4"
    final_output = f"{base}_discordpressed.mp4"

    print(f"\nProcessing: {input_path} (Preset: {ENCODING_PRESET})")
    width, height, duration, original_fps = get_video_info(input_path)

    if None in (width, height, duration):
        print("Could not retrieve essential video info (width, height, or duration). Aborting conversion.")
        return

    fps_display = f"{original_fps:.2f}" if original_fps else "N/A"
    print(f"Resolution: {width}x{height}, Duration: {duration:.2f}s, Original FPS: {fps_display}")

    vf_filters = []
    if height > MAX_HEIGHT_UNTIL_HALVE:
        scale_filter_value = "scale=trunc(iw/2/2)*2:trunc(ih/2/2)*2"
        vf_filters.append(scale_filter_value)
        print(f"Scaling: Video height {height}px > {MAX_HEIGHT_UNTIL_HALVE}px. Applying filter: {scale_filter_value}")
    
    target_fps_val = None
    if original_fps:
        target_fps_val = calculate_target_framerate(original_fps)
        if target_fps_val:
            fps_filter_value = f"fps=fps={target_fps_val:.2f}"
            vf_filters.append(fps_filter_value)
            print(f"Framerate: Original {original_fps:.2f}fps. Adjusting to {target_fps_val:.2f}fps.")
        else:
            print(f"Framerate: Original {original_fps:.2f}fps. No change needed.")

    vf_args = ["-vf", ",".join(vf_filters)] if vf_filters else []

    common_video_options = [
        "-c:v", "libx264",
        "-preset", ENCODING_PRESET
    ]
    common_ffmpeg_options = [
        "-c:a", "aac", "-b:a", str(AUDIO_BITRATE),
        "-movflags", "+faststart", "-hide_banner", "-loglevel", "error", "-stats"
    ]

    print("1. Trying default bitrate encoding (single pass)...")
    cmd_pass1_default = [
        "ffmpeg", "-y", "-i", input_path,
        *common_video_options,
        "-b:v", str(DEFAULT_VIDEO_BITRATE),
        *common_ffmpeg_options,
        *vf_args,
        temp_output
    ]
    try:
        subprocess.run(cmd_pass1_default, check=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error during default bitrate encoding: {e}")
        print(f"ffmpeg stderr: {e.stderr.decode(errors='ignore')}")
        if os.path.exists(temp_output): 
            try: os.remove(temp_output)
            except OSError as rm_err: print(f"Could not remove temp file {temp_output}: {rm_err}")
        return

    if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
        print("Error: First pass encoding failed to produce a valid output file.")
        if os.path.exists(temp_output): 
            try: os.remove(temp_output)
            except OSError as rm_err: print(f"Could not remove temp file {temp_output}: {rm_err}")
        return

    final_size_mb = os.path.getsize(temp_output) / (1024 * 1024)

    if final_size_mb <= MAX_SIZE_MB:
        print(f"Output is {final_size_mb:.2f}MB — keeping it.")
        if os.path.exists(final_output): 
            try: os.remove(final_output)
            except OSError as e_rm: print(f"Could not remove existing {final_output}: {e_rm}")
        try:
            os.rename(temp_output, final_output)
        except OSError: 
            try:
                shutil.copy2(temp_output, final_output)
                os.remove(temp_output)
                print("Used copy & delete as rename fallback.")
            except Exception as e_copy:
                print(f"Error renaming/copying {temp_output} to {final_output}: {e_copy}")
                return
    else:
        print(f"Output is {final_size_mb:.2f}MB — too large. Re-encoding for ≤ {MAX_SIZE_MB}MB (2-pass).")
        if os.path.exists(temp_output): 
            try: os.remove(temp_output)
            except OSError as rm_err: print(f"Could not remove oversized temp file {temp_output}: {rm_err}")

        target_bitrate = calculate_target_bitrate(duration, MAX_SIZE_MB, AUDIO_BITRATE)
        print(f"Targeting video bitrate: {target_bitrate / 1000:.0f} kbps for 2-pass.")

        if target_bitrate < 100_000:
            print(f"Warning: Calculated target video bitrate ({target_bitrate / 1000:.0f} kbps) is very low. Quality may be poor.")

        pass_log_prefix = f"{base}_2passlog"
        pass1_cmd = [
            "ffmpeg", "-y", "-i", input_path,
            *common_video_options,
            "-b:v", str(target_bitrate),
            "-pass", "1", "-passlogfile", pass_log_prefix, "-an",
            *vf_args, "-f", "mp4", os.devnull if os.name != 'nt' else "NUL",
            "-hide_banner", "-loglevel", "error"
        ]
        pass2_cmd = [
            "ffmpeg", "-y", "-i", input_path,
            *common_video_options,
            "-b:v", str(target_bitrate),
            "-pass", "2", "-passlogfile", pass_log_prefix,
            *common_ffmpeg_options,
            *vf_args,
            final_output
        ]

        print("Running 2-pass: Pass 1...")
        try:
            subprocess.run(pass1_cmd, check=True, stderr=subprocess.PIPE)
            print("Running 2-pass: Pass 2...")
            subprocess.run(pass2_cmd, check=True, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"Error during 2-pass encoding: {e}")
            print(f"ffmpeg stderr: {e.stderr.decode(errors='ignore')}")
            if os.path.exists(final_output): 
                try: os.remove(final_output)
                except OSError as rm_err: print(f"Could not remove failed final_output {final_output}: {rm_err}")
        finally:
            for ext in ['', '.log', '.log.mbtree', '.log.temp']:
                log_file = f"{pass_log_prefix}{ext}"
                if os.path.exists(log_file):
                    try: os.remove(log_file)
                    except OSError as e_remove: print(f"Warning: Could not remove log file {log_file}: {e_remove}")
            if os.path.exists(temp_output):
                try: os.remove(temp_output)
                except OSError as e_remove: print(f"Warning: Could not remove leftover temp_output {temp_output}: {e_remove}")

    if os.path.exists(final_output) and os.path.getsize(final_output) > 0:
        final_size_check_mb = os.path.getsize(final_output) / (1024 * 1024)
        print(f"Final file: {final_output} ({final_size_check_mb:.2f}MB)")
        if final_size_check_mb > MAX_SIZE_MB + 0.5:
             print(f"Warning: Final file size ({final_size_check_mb:.2f}MB) is over target {MAX_SIZE_MB}MB.")
    elif not os.path.exists(final_output) or os.path.getsize(final_output) == 0 :
        print(f"Error: Final output file {final_output} was not created or is empty.")
        if os.path.exists(final_output) and os.path.getsize(final_output) == 0:
            try: os.remove(final_output)
            except OSError as e_remove: print(f"Warning: Could not remove empty final_output {final_output}: {e_remove}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script_name.py <video_file1> [video_file2 ...]")
        sys.exit(1)

    for path_arg in sys.argv[1:]:
        convert_video(path_arg)
    
    print(f"\nAll conversions finished. Used preset: {ENCODING_PRESET}")
