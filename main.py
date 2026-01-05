import os
import threading
import yt_dlp
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard

class MyLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): print(f"YT-DLP Error: {msg}")
    def info(self, msg): pass

class DownloaderRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=20, spacing=15, **kwargs)
        
        self.save_path = "/storage/emulated/0/Download/Videos"
        self.ensure_directory()

        self.add_widget(Label(text='YouTube Downloader Pro', font_size='22sp', size_hint_y=None, height=50))

        self.url_input = TextInput(hint_text='Вставьте ссылку сюда', multiline=False, size_hint_y=None, height=110, font_size='16sp')
        self.add_widget(self.url_input)

        row = BoxLayout(size_hint_y=None, height=100, spacing=10)
        self.btn_paste = Button(text='📋 Вставить', on_release=self.paste_url)
        self.btn_fetch = Button(text='🔍 Найти', on_release=self.start_fetch, background_color=(0, 0.6, 1, 1))
        row.add_widget(self.btn_paste)
        row.add_widget(self.btn_fetch)
        self.add_widget(row)

        self.info_label = Label(text=f"Папка: {self.save_path}", font_size='12sp', halign='center')
        self.add_widget(self.info_label)

        self.quality_spinner = Spinner(text='Выберите качество', values=(), size_hint_y=None, height=100, disabled=True)
        self.add_widget(self.quality_spinner)

        self.status_label = Label(text='Готов', size_hint_y=None, height=40)
        self.add_widget(self.status_label)
        
        self.progress_bar = ProgressBar(max=100, size_hint_y=None, height=20)
        self.add_widget(self.progress_bar)

        self.btn_download = Button(text='🚀 СКАЧАТЬ', size_hint_y=None, height=130, disabled=True, background_color=(0, 0.7, 0, 1), font_size='20sp')
        self.btn_download.bind(on_release=self.start_download)
        self.add_widget(self.btn_download)

        self.formats_map = {}

    def ensure_directory(self):
        try:
            os.makedirs(self.save_path, exist_ok=True)
        except:
            self.save_path = str(Path.home() / "Downloads")

    def play_done_sound(self):
        try:
            from jnius import autoclass
            ToneGenerator = autoclass('android.media.ToneGenerator')
            AudioManager = autoclass('android.media.AudioManager')
            tone = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 100)
            tone.startTone(24) 
        except: pass

    def paste_url(self, instance):
        self.url_input.text = Clipboard.paste().strip()

    def start_fetch(self, instance):
        url = self.url_input.text.strip()
        if not url:
            return
        self.status_label.text = "🔍 Поиск форматов..."
        self.btn_fetch.disabled = True
        threading.Thread(target=self.fetch_thread, args=(url,), daemon=True).start()

    def fetch_thread(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'logger': MyLogger()}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                valid = {"🎵 Только аудио (MP3)": "audio_only", "Best": "bestvideo+bestaudio/best"}
                
                seen_res = set()
                for f in reversed(formats):
                    if f.get('vcodec') == 'none':
                        continue
                    res = f.get('height')
                    if not res:
                        continue
                    
                    label = f"{res}p"
                    if label in seen_res:
                        continue
                    
                    fmt_id = f['format_id']
                    if f.get('acodec') == 'none':
                        fmt_id += '+bestaudio/best'
                    
                    valid[label] = fmt_id
                    seen_res.add(label)

                title = info.get('title', 'Unknown Title')
                Clock.schedule_once(lambda dt: self.update_after_fetch(title, valid))
        except Exception as e:
            err_msg = str(e)
            Clock.schedule_once(lambda dt: self.show_error(err_msg))

    def update_after_fetch(self, title, formats):
        self.info_label.text = f"🎬 {title[:50]}..."
        self.formats_map = formats
        keys = sorted(formats.keys())
        if keys:
            self.quality_spinner.values = keys
            self.quality_spinner.text = keys[0]
            self.quality_spinner.disabled = False
            self.btn_download.disabled = False
        self.btn_fetch.disabled = False
        self.status_label.text = "✅ Готов к загрузке"

    def show_error(self, msg):
        self.status_label.text = "❌ Ошибка"
        self.info_label.text = msg[:100]
        self.btn_fetch.disabled = False
        self.btn_download.disabled = False

    def start_download(self, instance):
        url = self.url_input.text.strip()
        fmt_val = self.formats_map.get(self.quality_spinner.text)
        if not fmt_val:
            return
        self.btn_download.disabled = True
        threading.Thread(target=self.download_thread, args=(url, fmt_val), daemon=True).start()

    def download_thread(self, url, fmt_val):
        def hook(d):
            if d['status'] == 'downloading':
                p = d.get('_percent_str', '0%').replace('%', '').strip()
                try:
                    Clock.schedule_once(lambda dt: self.update_progress(float(p)))
                except:
                    pass
            elif d['status'] == 'finished':
                Clock.schedule_once(lambda dt: self.set_status("⚙️ Финализация..."))

        opts = {
            'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),
            'logger': MyLogger(),
            'progress_hooks': [hook],
            'continuedl': True,
            'nocheckcertificate': True,
        }

        if fmt_val == "audio_only":
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            opts['format'] = fmt_val

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.play_done_sound()
            Clock.schedule_once(lambda dt: self.finish_all())
        except Exception as e:
            err_msg = str(e)
            Clock.schedule_once(lambda dt: self.show_error(err_msg))

    def update_progress(self, val):
        self.progress_bar.value = val
        self.status_label.text = f"⬇️ Скачивание: {val:.1f}%"

    def set_status(self, txt):
        self.status_label.text = txt

    def finish_all(self):
        self.status_label.text = "✅ Завершено!"
        self.progress_bar.value = 100
        self.btn_download.disabled = False

class YTApp(App):
    def build(self):
        return DownloaderRoot()

if __name__ == '__main__':
    YTApp().run()
