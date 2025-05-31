# discordpressor

An FFmpeg compressor script to easily send files within Discord's 10MB limit.

This program was made for Windows, but should be able to run on Linux with some slight modifications.

## Installation

### Requirements

- FFmpeg installed in your [PATH](https://github.com/aaatipamula/ffmpeg-install?tab=readme-ov-file#ffmpeg-windows-install).
- Python 3 (can be installed from the Microsoft Store if not already on your PC).
- The ZIP file from the `Releases` tab on the right (`discordpressor-v*.zip`).

### Setup

1. Unpack the ZIP file. Inside should be two files: `discordpressor.bat` and `discordpressorScript.py`.
2. Place `discordpressorScript.py` somewhere where you won't accidentally remove it, like in the Documents folder.
3. Open `discordpressor.bat` in your editor of choice, and change the `C:\path\to\discordpressorScript.py` in the second line to the actual location where you put your `discordpressorScript.py`.
4. Place `discordpressor.bat` wherever you want, though I recommend putting it on the Desktop for easy access.

## Usage

Drag whichever video you want to convert on top of the `discordpressor.bat` file, which will automatically convert your video to one you can easily send on Discord.

## Customization

There are a few values you can play around with in `discordpressorScript.py`, under `# Constants`. Here is an explenation for what each of them do:

- `MAX_SIZE_MB`: controls the maximum size you want your converted video to be (warning: result might deviate by max. 0.5 MB)
- `DEFAULT_VIDEO_BITRATE`: controls the default bitrate of videos, as long as they're not overwritten by the maximum file size (so it's the desired bitrate for short videos basically)
- `AUDIO_BITRATE`: controls the bitrate of the converted audio, which is in the AAC codec by default
- `MAX_HEIGHT_UNTIL_HALVE`: if your input video's height exceeds this value, the resolution will be halved to decrease artefacts with low bitrates
- `ENCODING_PRESET`: the speed at which FFmpeg transcodes the video, so you can choose how you want to balance time and quality; the slower the preset, the more quality per bitrate

## Details

Videos used with this program will be converted with FFmpeg to an H264 AAC MP4 file. If the framerate of the input video exceeds 50, it will be halved, and if it exceeds 100, it will be halved twice (so 1/4 the original framerate). It also halves the resolution if it's higher than `MAX_HEIGHT_UNTIL_HALVE` (1440 by default).
