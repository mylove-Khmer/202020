import os
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import openai
import google.generativeai as genai
from elevenlabs import ElevenLabs
import subprocess

app = Flask(__name__)

# กำหนด API Keys របស់អ្នក
OPENAI_API_KEY = "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"
GEMINI_API_KEY = "AQ.Ab8RN6KqxCP92Dur9hb0Na7WOYMIQjhsALD5d3dTtMPqfEtwhQ"
ELEVENLABS_API_KEY = "sk_6a12640db0f72d849867f098e11f465eb760885c9fdf6af8"

# ភ្ជាប់ Gemini API
genai.configure(api_key=GEMINI_API_KEY)
client_openai = openai.OpenAI(api_key=OPENAI_API_KEY)
client_elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/process-video', methods=['POST'])
def process_video():
    if 'video' not in request.files or 'voice' not in request.form:
        return jsonify({'error': 'Missing video or voice type'}), 400
    
    file = request.files['video']
    voice_type = request.form['voice'] # 'male' ឬ 'female'
    
    filename = secure_filename(file.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted_audio.mp3')
    kh_audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'khmer_audio.mp3')
    output_video_path = os.path.join(app.config['UPLOAD_FOLDER'], 'output_' + filename)
    
    file.save(video_path)
    
    try:
        # ១. ទាញយកសំឡេងពីវីដេអូ និងបម្លែងជាអត្ថបទ (OpenAI Whisper)
        subprocess.run(['ffmpeg', '-y', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path], check=True)
        with open(audio_path, 'rb') as audio_file:
            transcript = client_openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        
        # ២. ប្រើប្រាស់ Gemini API ដើម្បីបកប្រែ និងសម្រាយជាភាសាខ្មែរ
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Translate and summarize the following script into natural, engaging spoken Khmer for story narration: {transcript.text}"
        response = model.generate_content(prompt)
        khmer_script = response.text
        
        # ៣. ប្រើប្រាស់ ElevenLabs API ដើម្បីបង្កើតសំឡេងនិយាយខ្មែរ (ជ្រើសរើសសំឡេងប្រុស/ស្រី)
        voice_id = "21m00Tcm4TlvDq8ikWAM" if voice_type == 'female' else "AZnzlk1XvdvUeBnXmlld" # ជំនួស Voice ID តាមចង់បាន
        audio_generator = client_elevenlabs.text_to_speech.convert(
            voice_id=voice_id,
            output_format="mp3_44100_128",
            text=khmer_script,
            model_id="eleven_multilingual_v2"
        )
        
        with open(kh_audio_path, 'wb') as f:
            for chunk in audio_generator:
                f.write(chunk)
                
        # ៤. ប្រើប្រាស់ FFmpeg ដើម្បីលុបសំឡេងដើម និងបញ្ចូលសំឡេងខ្មែរថ្មីចូលវីដេអូ
        subprocess.run([
            'ffmpeg', '-y', '-i', video_path, '-i', kh_audio_path,
            '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', output_video_path
        ], check=True)
        
        return jsonify({'success': True, 'download_url': f'/download/{os.path.basename(output_video_path)}'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
