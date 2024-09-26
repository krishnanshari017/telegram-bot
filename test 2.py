import requests
import subprocess
import re
import json
import os

API_TOKEN = '7789690322:AAGU9iobBaOCYJLMcvD7yi-c-G_x0hvMTlc'
BASE_URL = f'https://api.telegram.org/bot{API_TOKEN}/'

# Store user state: video URL and awaiting quality response
user_states = {}

def send_message(chat_id, text, reply_markup=None):
    url = BASE_URL + 'sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    response = requests.post(url, json=payload)
    print(f"Sending message to {chat_id}: {text}")
    if response.status_code != 200:
        print("Failed to send message:", response.text)

def merge_video_audio(video_file, audio_file, output_file):
    if os.path.exists(video_file) and os.path.exists(audio_file):
        command = [
            'ffmpeg', '-i', video_file, '-i', audio_file,
            '-c:v', 'copy', '-c:a', 'copy', output_file
        ]
        print(f"Running merge command: {' '.join(command)}")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            print(f"Error merging files: {result.stderr.decode()}")
        else:
            print(f"Successfully merged {video_file} and {audio_file} into {output_file}")
    else:
        print("One of the files does not exist.")

def download_video(video_url, quality, chat_id):
    video_file = f'{quality}.webm'
    audio_file = f'{quality}.mp3'  # Use mp3 for audio
    output_file = 'output.mkv'  # The final merged file

    # Command to download video and audio
    command = [
        'yt-dlp',
        '-f', f'{quality}+bestaudio/bestaudio',
        '-o', video_file,
        video_url
    ]
    
    print(f"Running command to download video: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    
    print("Video download stdout:", result.stdout)
    print("Video download stderr:", result.stderr)

    # Check if the video file exists
    if os.path.exists(video_file):
        print(f"Video file '{video_file}' downloaded successfully.")
    else:
        print(f"Video file '{video_file}' was not downloaded.")

    # Attempt to download audio in mp3 format if audio file doesn't exist
    if not os.path.exists(audio_file):
        print(f"Audio file '{audio_file}' was not downloaded. Trying to download as mp3...")
        command_audio = [
            'yt-dlp',
            '-f', 'bestaudio[ext=mp3]',
            '-o', audio_file,
            video_url
        ]
        result_audio = subprocess.run(command_audio, capture_output=True, text=True)
        print("Audio download stdout:", result_audio.stdout)
        print("Audio download stderr:", result_audio.stderr)
    
    # Check if the audio file now exists
    if os.path.exists(audio_file):
        print(f"Audio file '{audio_file}' downloaded successfully.")
    else:
        print(f"Audio file '{audio_file}' was not downloaded.")
        # Attempt to download audio in other formats if mp3 fails
        print("Trying to download audio in other formats...")
        command_audio_alternative = [
            'yt-dlp',
            '-f', 'bestaudio',
            '-o', audio_file,
            video_url
        ]
        result_audio_alt = subprocess.run(command_audio_alternative, capture_output=True, text=True)
        print("Alternative audio download stdout:", result_audio_alt.stdout)
        print("Alternative audio download stderr:", result_audio_alt.stderr)

        # Final check
        if os.path.exists(audio_file):
            print(f"Audio file '{audio_file}' downloaded successfully using alternative method.")
        else:
            print(f"Audio file '{audio_file}' could not be downloaded with any method.")

    # Merge video and audio only if both exist
    if os.path.exists(video_file) and os.path.exists(audio_file):
        merge_video_audio(video_file, audio_file, output_file)
        send_video(chat_id, output_file)
    else:
        error_message = 'Failed to download video or audio files. Please try again.'
        send_message(chat_id, error_message)
        print("Download error: One or both files are missing.")
        reply_markup = {
            "inline_keyboard": [
                [{"text": "Try Again", "callback_data": f"retry:{quality}"}]
            ]
        }
        send_message(chat_id, 'Download failed. Would you like to try again?', reply_markup)

def send_video(chat_id, video_file):
    url = BASE_URL + 'sendVideo'
    with open(video_file, 'rb') as video:
        files = {'video': video}
        payload = {'chat_id': chat_id}
        response = requests.post(url, data=payload, files=files)
        
    if response.status_code == 200:
        send_message(chat_id, 'Video sent successfully!')
    else:
        send_message(chat_id, 'Failed to send video.')
        print("Send video error:", response.text)

def get_video_qualities(video_url):
    command = [
        'yt-dlp',
        '-F',
        video_url
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.stdout

def parse_mp4_qualities(qualities_output):
    common_qualities = ['144p', '240p', '360p', '480p', '720p', '1080p', '2160p']
    available_formats = []
    
    for line in qualities_output.splitlines():
        match = re.match(r'^\s*(\d+|\w+)\s+(\S+)\s+.*?(\d+p)', line)
        if match:
            format_id = match.group(1)
            quality = match.group(3)
            if quality in common_qualities:
                available_formats.append((format_id, quality))
    
    return available_formats

def handle_update(update):
    chat_id = update['message']['chat']['id']
    text = update['message'].get('text')

    print("Update received:", update)

    if text == '/start':
        send_message(chat_id, 'Please send me the video link.')
        user_states.pop(chat_id, None)

    elif re.match(r'https?://\S+', text):
        qualities = get_video_qualities(text)
        
        if "ERROR" not in qualities:
            mp4_qualities = parse_mp4_qualities(qualities)

            if mp4_qualities:
                buttons = []
                for i in range(0, len(mp4_qualities), 3):
                    row = [{"text": f"{quality} (mp4)", "callback_data": f"{format_id}"} for format_id, quality in mp4_qualities[i:i + 3]]
                    buttons.append(row)
                reply_markup = {"inline_keyboard": buttons}
                send_message(chat_id, 'Please choose a video quality:', reply_markup=reply_markup)
                user_states[chat_id] = {'video_url': text, 'awaiting_quality': True}
            else:
                send_message(chat_id, 'No MP4 formats available for this video.')
        else:
            send_message(chat_id, 'Failed to fetch video qualities. Please check the link.')
    
    else:
        send_message(chat_id, 'Please send a valid video link.')

def handle_callback_query(callback_query):
    chat_id = callback_query['message']['chat']['id']
    data = callback_query['data']

    if chat_id not in user_states:
        send_message(chat_id, 'Please send a video link first and select a quality.')
        return

    if data.startswith("retry:"):
        quality = data.split(":")[1]
        video_url = user_states[chat_id]['video_url']
        send_message(chat_id, 'Retrying download...')
        download_video(video_url, quality, chat_id)

    elif user_states[chat_id].get('awaiting_quality'):
        video_url = user_states[chat_id]['video_url']
        quality = data
        send_message(chat_id, 'Downloading your video...')
        download_video(video_url, quality, chat_id)

def main():
    offset = None
    while True:
        url = BASE_URL + 'getUpdates'
        if offset:
            url += f'?offset={offset}'
        print("Fetching updates...")
        response = requests.get(url)
        updates = response.json().get('result', [])
        
        for update in updates:
            if 'message' in update:
                handle_update(update)
            elif 'callback_query' in update:
                handle_callback_query(update['callback_query'])
            offset = update['update_id'] + 1

if __name__ == '__main__':
    main()
