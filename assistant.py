import speech_recognition as sr
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import threading
import json
import pyttsx3
import random

# Set to your ChromeDriver path if not in PATH; '' if in PATH
CHROMEDRIVER_PATH = ''  # e.g., r'./chromedriver/chromedriver.exe' for Windows

class AIVoiceAssistant:
    def __init__(self):
        self.status_file = "sunday_status.json"
        self.conv_log_file = "conversation_log.txt"
        self.listening = True
        self.wake_word = "sunday"
        self.consecutive_failures = 0
        self.max_failures = 5  # Recalibrate after this many misses
        
        self.setup_tts()
        self.log_conversation("System", "Sunday AI starting with simple TTS system")

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        self.recognizer.energy_threshold = 3000  # Adjust lower (2000) if noisy
        self.recognizer.pause_threshold = 1.0
        self.recognizer.dynamic_energy_threshold = True
        
        self.calibrate_microphone()

        self.chrome_options = Options()
        self.chrome_options.add_argument("--use-fake-ui-for-media-stream")
        self.chrome_options.add_argument("--disable-web-security")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_argument("--window-size=1200,800")
        
        self.driver = None

        browser_thread = threading.Thread(target=self.open_browser, daemon=True)
        browser_thread.start()

        time.sleep(3)
        listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
        listen_thread.start()

        self.write_status('ready', '', '')
        self.speak("I'm listening for you. Just say 'Sunday' when you need me!")
        self.speak("Hello! I'm Sunday, your yoga assistant. I'm here and ready to help you with your wellness journey. Just say 'Sunday' followed by what you'd like to do!")

    def setup_tts(self):
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 1.0)
            self.log_conversation("System", "TTS configured")
        except Exception as e:
            self.log_conversation("System", f"TTS setup error: {e}")
            self.tts_engine = None

    def _system_tts(self, text):
        """Fallback TTS: Just print (works everywhere)"""
        print(f"🔊 AI: {text}")

    def speak(self, text):
        if not text or not self.listening:
            return False
            
        self.log_conversation("AI", text)
        self.write_status('speaking', '', text)
        
        try:
            if self.tts_engine:
                def speak_thread():
                    try:
                        engine = pyttsx3.init()  # Re-init to avoid segfaults
                        engine.setProperty('rate', 150)
                        engine.setProperty('volume', 1.0)
                        engine.say(text)
                        engine.runAndWait()
                    except Exception as e:
                        print(f"TTS Error: {e}")
                        self._system_tts(text)
                
                thread = threading.Thread(target=speak_thread, daemon=True)
                thread.start()
                return True
            else:
                self._system_tts(text)
                return True
                
        except Exception as e:
            self.log_conversation("System", f"Speak error: {e}")
            self._system_tts(text)
            return False

    def calibrate_microphone(self):
        try:
            self.log_conversation("System", "Calibrating microphone... Please wait.")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=3)
            self.log_conversation("System", "Microphone calibrated successfully")
            self.consecutive_failures = 0
        except Exception as e:
            self.log_conversation("System", f"Microphone calibration failed: {e}")

    def log_conversation(self, speaker, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {speaker}: {message}\n"
        with open(self.conv_log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(log_entry.strip())

    def write_status(self, action, user_command='', ai_response=''):
        try:
            data = {
                'action': action,
                'timestamp': time.time(),
                'user_command': user_command,
                'ai_response': ai_response
            }
            with open(self.status_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            self.log_conversation("System", f"Status write error: {e}")

    def get_acknowledgement(self):
        acknowledgements = [
            "Sure thing!", "I'm on it!", "Right away!", "Absolutely!", "Got it!", "Okay!", "No problem!"
        ]
        return random.choice(acknowledgements)

    def open_browser(self):
        max_retries = 3
        server_url = "http://127.0.0.1:5000"
        
        for attempt in range(max_retries):
            try:
                if CHROMEDRIVER_PATH:
                    from selenium.webdriver.chrome.service import Service
                    service = Service(CHROMEDRIVER_PATH)
                    self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
                else:
                    self.driver = webdriver.Chrome(options=self.chrome_options)
                self.driver.get(server_url)
                
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                time.sleep(4)
                self.log_conversation("System", f"Browser connected to {server_url}")
                self.speak("Perfect! I'm all connected and ready to help you.")
                return
            except Exception as e:
                self.log_conversation("System", f"Browser open failed (attempt {attempt + 1}): {e}")
                if self.driver:
                    self.driver.quit()
                    self.driver = None
                time.sleep(2)
        
        self.speak("Sorry, couldn't connect to the web app. Make sure the server is running on port 5000.")

    def navigate_section(self, section):
        if not self.driver:
            return False
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "app"))  # Wait for JS app
            )
            
            button_texts = {
                'pose_library': 'Pose Library',
                'ar_correction': 'AR Correction',
                'routine': 'Routine',
                'assistant': 'Assistant'
            }
            if section in button_texts:
                btn = self.driver.find_element(By.XPATH, f"//button[contains(text(), '{button_texts[section]}')]")
                btn.click()
                time.sleep(2)
                return True
            
            # Fallback: JS execution (assumes app.showSection in index.html)
            self.driver.execute_script(f"if (typeof app !== 'undefined') {{ app.showSection('{section}'); }}")
            time.sleep(2)
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            self.log_conversation("System", f"Navigation failed for {section}: {e}")
            return False

    def listen_for_speech(self, timeout=5, phrase_time_limit=6):
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            return audio
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            self.log_conversation("System", f"Listen error: {e}")
            return None

    def recognize_audio(self, audio):
        try:
            text = self.recognizer.recognize_google(audio).lower()
            return text
        except sr.UnknownValueError:
            self.consecutive_failures += 1
            return None
        except sr.RequestError as e:
            self.log_conversation("System", f"Recognition error: {e}")
            return None

    def process_command(self, command):
        acknowledgement = self.get_acknowledgement()
        
        if any(word in command for word in ['open pose library', 'poses', 'asanas']):
            success = self.navigate_section('pose_library')
            self.speak(f"{acknowledgement} Opening the yoga pose library." if success else "Opening pose library...")

        elif any(word in command for word in ['ar', 'correction', 'camera', 'tracking', 'posture']):
            success = self.navigate_section('ar_correction')
            self.speak(f"{acknowledgement} Starting AR posture correction. Stand 6 feet from your camera!" if success else "Setting up camera...")

        elif any(word in command for word in ['routine', 'plan', 'workout', 'schedule']):
            success = self.navigate_section('routine')
            self.speak(f"{acknowledgement} Opening your personalized routine." if success else "Loading your routine...")

        elif any(word in command for word in ['assistant', 'chat', 'help', 'ai', 'virtual assistant']):
            success = self.navigate_section('assistant')
            self.speak(f"{acknowledgement} Opening chat. What would you like to know?" if success else "Opening chat...")

        elif any(word in command for word in ['tadasana', 'mountain']):
            self.speak(f"{acknowledgement} Starting Tadasana.")
            self.navigate_section('ar_correction')

        elif any(word in command for word in ['vrikshasana', 'tree']):
            self.speak(f"{acknowledgement} Starting Tree Pose.")
            self.navigate_section('ar_correction')

        elif any(word in command for word in ['namastey', 'prayer']):
            self.speak(f"{acknowledgement} Starting Namastey.")
            self.navigate_section('ar_correction')

        elif any(word in command for word in ['test', 'status']):
            self.speak("I'm ready! Try 'open pose library' or 'start AR correction'.")

        elif any(word in command for word in ['thank', 'thanks']):
            self.speak("You're welcome! Namaste.")

        elif any(word in command for word in ['hello', 'hi', 'hey']):
            self.speak("Hello! How can I help today?")

        elif any(word in command for word in ['stop', 'quit', 'exit', 'shutdown', 'goodbye']):
            self.speak("Thank you for your practice! Namaste!")
            time.sleep(2)
            self.stop()

        else:
            self.speak("I didn't catch that. Try again, like 'open pose library'.")

    def listen_loop(self):
        self.log_conversation("System", "Listening for wake word 'Sunday'...")
        
        wake_responses = [
            "Yes, I'm listening! What would you like to do?",
            "I'm here! How can I assist your practice?",
            "Yes, tell me how I can help!",
            "Hello! What shall we work on together?"
        ]
        
        similar_words = ['sundae', 'sundays', 'sunday\'s', 'someday']
        
        while self.listening:
            try:
                audio = self.listen_for_speech(timeout=5, phrase_time_limit=6)
                if audio:
                    text = self.recognize_audio(audio)
                    if text:
                        self.consecutive_failures = 0  # Reset on success
                        
                        if self.wake_word in text.lower():
                            self.log_conversation("System", f"Wake word detected: {text}")
                            self.speak(random.choice(wake_responses))
                            
                            # Separate listen for command (key fix!)
                            audio_cmd = self.listen_for_speech(timeout=10, phrase_time_limit=15)
                            if audio_cmd:
                                command = self.recognize_audio(audio_cmd)
                                if command:
                                    self.process_command(command.lower())
                                else:
                                    self.speak("I didn't catch the command. Try again after 'Sunday'.")
                            else:
                                self.speak("I'm ready when you are.")
                        elif any(word in text for word in similar_words):
                            self.speak("Did you mean Sunday? Say it clearly if you need me.")
                            
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.max_failures:
                    self.log_conversation("System", "Recalibrating due to failures")
                    self.calibrate_microphone()
                
                time.sleep(0.5)
                
            except Exception as e:
                self.log_conversation("System", f"Listen loop error: {e}")
                time.sleep(1)

    def stop(self):
        self.listening = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        self.log_conversation("System", "Sunday AI stopped")
        os._exit(0)

if __name__ == "__main__":
    try:
        assistant = AIVoiceAssistant()
        while assistant.listening:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        if 'assistant' in locals():
            assistant.stop()
    except Exception as e:
        print(f"Fatal error: {e}")