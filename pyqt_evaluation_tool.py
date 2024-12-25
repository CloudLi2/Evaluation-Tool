import sys
import os
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QTextEdit, QLabel, \
                            QVBoxLayout, QWidget, QHBoxLayout, QSlider, QListWidget
from PyQt5.QtCore import QTimer, Qt
import simpleaudio as sa
import wave
from pydub import AudioSegment


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        """Rewrite the mousePressEvent method to get the slider value by clicking
        """
        if event.button() == Qt.LeftButton:
            x = event.pos().x()
            slider_length = self.size().width()
            slider_min = self.minimum()
            slider_max = self.maximum()

            new_value = round((x / slider_length) * (slider_max - slider_min) + slider_min)
            self.setValue(new_value)
            self.sliderReleased.emit()
        super().mousePressEvent(event)
        

class PyqtEvaluationTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Evaluation Tool")
        self.setup_ui()
        self.initialize_variables()
        self.setup_timer()
        self.reference_audio_files = []
        
    def setup_timer(self):
        """timer for updating the slider
        """
        self.timer = QTimer(self)
        self.timer.setInterval(10)  # Timer interval set to 10 milliseconds
        self.timer.timeout.connect(self.update_slider)
        
    def initialize_variables(self):
        self.audio_files = []
        self.current_index = 0
        self.audio_thread = None
        self.results = []  # list to store the results
        self.audio_segment = None
        self.play_obj = None
        self.num_frames = None
        self.texts = []
        self.audio_position = 0
        self.audio_duration_ms = 0
        
    def setup_ui(self):
        """UI setup
        """
        # dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Microsoft YaHei UI;
                font-weight: bold;
            }
            QLabel {
                font-size: 12pt;
                font-family: Microsoft YaHei UI;
                font-weight: bold;
                color: #d4d4d4;
            }
            QTextEdit {
                font-size: 16pt;
                font-family: Microsoft YaHei;
                font-weight: normal;
                background-color: #252526;
                color: #d4d4d4;
            }
            QListWidget {
                font-size: 12pt;
                font-family: Arial;
                font-weight: normal;
                background-color: #252526;
                color: #d4d4d4;
            }
        """)
        
        desktop = QApplication.desktop()
        self.setGeometry(
            desktop.width() // 4 - 500,
            desktop.height() // 2 - 400,
            1080,
            800
        )
        
        # create main layout
        main_layout = QHBoxLayout()
        
        # left layout for audio list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("font-size: 11pt;")
        self.list_widget.itemClicked.connect(self.on_item_clicked)

        # right layout for text display, note, progress bar, and buttons
        right_layout = QVBoxLayout()
        
        # top layout for text label and switch button
        top_layout = QHBoxLayout()
        text_label = QLabel("Text：", self)
        text_label.setStyleSheet("font-size: 12pt;")
        top_layout.addWidget(text_label)
        
        self.switch_button = QPushButton("Switch layout", self)
        self.switch_button.setStyleSheet("font-size: 12pt; background-color: #009478;")
        self.switch_button.setFixedWidth(120)
        self.switch_button.clicked.connect(lambda: self.switch_layout())
        top_layout.addWidget(self.switch_button)
        
        right_layout.addLayout(top_layout)
        
        # text display
        self.text_display = QTextEdit(self)
        self.text_display.setReadOnly(True)
        self.text_display.setStyleSheet("font-size: 16pt;")
        right_layout.addWidget(self.text_display)
        
        # create layout for replay and play reference audio buttons
        reference_layout = QHBoxLayout()
        note_label = QLabel("Note：", self)
        note_label.setStyleSheet("font-size: 12pt;")
        reference_layout.addWidget(note_label)
        
        self.replay_button = QPushButton("Replay", self)
        self.replay_button.setFixedHeight(40)
        self.replay_button.setStyleSheet("font-size: 16px; background-color: #008fb8;")
        self.replay_button.clicked.connect(self.replay_audio)
        reference_layout.addWidget(self.replay_button)
        
        self.play_reference_button = QPushButton("Play reference audio", self)
        self.play_reference_button.setStyleSheet("font-size: 12pt; background-color: #005bbd;")
        self.play_reference_button.setFixedHeight(40)
        self.play_reference_button.clicked.connect(self.play_reference_audio_button_clicked)
        reference_layout.addWidget(self.play_reference_button)
        
        right_layout.addLayout(reference_layout)
        
        # Note text box
        self.note = QTextEdit(self)
        self.note.setFixedHeight(100)
        self.note.setStyleSheet("font-size: 14pt;")
        right_layout.addWidget(self.note)
        
        # progress bar
        progressbar_layout = QHBoxLayout()
        self.progress_slider = ClickableSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderPressed.connect(self.seek_audio)
        progressbar_layout.addWidget(self.progress_slider)        
        
        right_layout.addLayout(progressbar_layout)
        
        # Next button
        self.next_button = QPushButton("Next audio", self)
        self.next_button.setFixedHeight(40)
        self.next_button.setStyleSheet("font-size: 16px; color: black; background-color: #cccccc;")
        self.next_button.clicked.connect(lambda: self.next_audio())
        right_layout.addWidget(self.next_button)

        # layout for 4 buttons
        button_layout = QHBoxLayout()
        self.TP_button = QPushButton("True Positive", self)
        self.TP_button.setFixedHeight(100)  # 增加高度
        self.TP_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #007509; 
                """)
        self.TP_button.clicked.connect(lambda: self.mark_result("TP"))
        button_layout.addWidget(self.TP_button)
        
        self.TN_button = QPushButton("True Negative", self)
        self.TN_button.setFixedHeight(100)  # 增加高度
        self.TN_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #00870a; 
                """)
        self.TN_button.clicked.connect(lambda: self.mark_result("TN"))
        button_layout.addWidget(self.TN_button)
                
        self.FP_button = QPushButton("False Positive", self)
        self.FP_button.setFixedHeight(100)
        self.FP_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #870100; 
                """)
        self.FP_button.clicked.connect(lambda: self.mark_result("FP"))
        button_layout.addWidget(self.FP_button)

        self.FN_button = QPushButton("False Negative", self)
        self.FN_button.setFixedHeight(100)
        self.FN_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #750100; 
                """)
        self.FN_button.clicked.connect(lambda: self.mark_result("FN"))
        button_layout.addWidget(self.FN_button)
        
        right_layout.addLayout(button_layout)
        
        # create layout for good and bad buttons
        button_layout2 = QHBoxLayout()
        self.TP_button2 = QPushButton("Good", self)
        self.TP_button2.setFixedHeight(100)
        self.TP_button2.setStyleSheet("""
                font-size: 22px;
                font-weight: bold;
                background-color: #007509;
                """)
        self.TP_button2.clicked.connect(lambda: self.mark_result("T"))
        button_layout2.addWidget(self.TP_button2)
        
        self.TN_button2 = QPushButton("Bad", self)
        self.TN_button2.setFixedHeight(100)
        self.TN_button2.setStyleSheet("""
                font-size: 22px;
                font-weight: bold;
                background-color: #870100;
                """)
        self.TN_button2.clicked.connect(lambda: self.mark_result("F"))
        button_layout2.addWidget(self.TN_button2)
        
        right_layout.addLayout(button_layout2)
        
        # layout for save and summary buttons
        save_exit_layout = QHBoxLayout()
        self.save_button = QPushButton("Save progress", self)
        self.save_button.setStyleSheet("font-size: 16px; background-color: #b34500")
        self.save_button.clicked.connect(self.save_progress)
        save_exit_layout.addWidget(self.save_button)
        
        # summary button
        self.exit_button = QPushButton("Get summary", self)
        self.exit_button.setStyleSheet("font-size: 16px; background-color: #7d2547;")
        self.exit_button.clicked.connect(self.save_and_summary)
        save_exit_layout.addWidget(self.exit_button)
        
        right_layout.addLayout(save_exit_layout)

        # add layouts to main layout
        main_layout.addWidget(self.list_widget, 1)
        main_layout.addLayout(right_layout, 5)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def play_reference_audio_button_clicked(self):
        if self.reference_audio_files and 0 <= self.current_index < len(self.reference_audio_files):
            self.load_reference_audio(self.reference_audio_files[self.current_index])
        else:
            print("No reference audio files or index out of range")

    def load_files(self, audio_folder, text_file, reference_audio_folder=None):
        """load audio files and text file
        """
        self.switch_layout()
        self.texts = []
        if os.path.exists(text_file):
            with open(text_file, 'r', encoding='utf-8') as f:
                self.texts = f.read().splitlines()
        else:
            print(f"Text file '{text_file}' not found.")
            return

        if os.path.exists(audio_folder):
            self.audio_files = [
                os.path.join(audio_folder, f) 
                for f in os.listdir(audio_folder) 
                if f.endswith('.wav')
            ]
            for file in self.audio_files:
                filename = os.path.basename(file)
                self.list_widget.addItem(filename)
            try:
                self.current_index = 0      # current_index starts from 0
                self.load_audio(self.audio_files[self.current_index])
            except ValueError:
                print("Index initialization error.")
                self.current_index = 0
        else:
            print(f"Audio folder '{audio_folder}' not found.")
            self.audio_files = []
            
        if reference_audio_folder and os.path.exists(reference_audio_folder):
            self.reference_audio_files = [
                os.path.join(reference_audio_folder, f) 
                for f in os.listdir(reference_audio_folder) 
                if f.endswith('.wav')
            ]
    
    def get_text_ultimate(self):
        """if first line ends with '.wav', read every n(n>1) lines(pattern1); otherwise, read every line(pattern2)
        """
        if not self.texts or self.current_index < 0:
            return "empty text file."
        
        current_line = 0
        line = self.texts[current_line].strip()
        if line.endswith('.wav'):
            # print("Reding txt every 4 lines")
            return self.get_text_pattern1()
        else:
            # print("Reding txt every line")
            return self.get_text_pattern2()

    def get_text_pattern1(self, n=4):
        """return the text block for each audio file, n=4 by default
        """
        if not self.texts or self.current_index < 0:
            return "no text available."
        current_line = 0
        audio_count = 0
        text_block = []
        
        while current_line < len(self.texts):
            if audio_count == self.current_index:
                current_line += 1
                for i in range(n-1):
                    text_line = self.texts[current_line].strip()
                    # print(text_line)
                    text_block.append(text_line)
                    current_line += 1
                break
            audio_count += 1
            current_line += 1
            
        return '\n'.join(text_block) if text_block else "cant find text end with '.wav', please check get_text function."
    
    def get_text_pattern2(self):
        """Read every line
        """
        if not self.texts or self.current_index < 0:
            return "no text available."
        
        return self.texts[self.current_index]
    
    def load_audio(self, file_path):
        """Load the audio file, set up the audio segment, and start playing from the beginning.
        """
        # Load the audio file using wave
        self.audio_read = wave.open(file_path, 'rb')
        self.audio_data = self.audio_read.readframes(self.audio_read.getnframes())
        self.num_channels = self.audio_read.getnchannels()
        self.bytes_per_sample = self.audio_read.getsampwidth()
        self.sample_rate = self.audio_read.getframerate()
        self.num_frames = self.audio_read.getnframes()
        self.audio_duration_ms = self.num_frames / self.sample_rate * 1000
        self.progress_slider.setRange(0, int(self.audio_duration_ms))
        
        # # Load the audio file using pydub
        # self.audio_segment = AudioSegment.from_wav(file_path)
        # self.audio_duration_ms = len(self.audio_segment)
        # self.progress_slider.setRange(0, int(self.audio_duration_ms))
        # Empty the note text box
        self.note.clear()
        # Start playing from the beginning
        self.play_audio(0)
    
    def load_reference_audio(self, file_path):
        # Load the audio file using wave
        self.reference_audio_read = wave.open(file_path, 'rb')
        self.reference_audio_data = self.reference_audio_read.readframes(self.reference_audio_read.getnframes())
        self.reference_audio_num_channels = self.reference_audio_read.getnchannels()
        self.reference_audio_bytes_per_sample = self.reference_audio_read.getsampwidth()
        self.reference_audio_sample_rate = self.reference_audio_read.getframerate()
        self.reference_audio_num_frames = self.reference_audio_read.getnframes()
        self.reference_audio_duration_ms = self.reference_audio_num_frames / self.reference_audio_sample_rate * 1000
        
        if self.reference_audio_data is None:
            print("reference audio not loaded.")
            return
        else:
            self.play_reference_audio(0)
        
        # # Load the audio file using pydub
        # self.reference_audio_segment = AudioSegment.from_wav(file_path)
        # if self.reference_audio_segment is None:
        #     print("reference audio not loaded.")
        #     return
        # else:
        #     self.reference_audio_duration_ms = len(self.reference_audio_segment)
        #     self.play_reference_audio(0)
    
    def play_audio(self, start_ms=0):
        """play audio function
        """
        # Stop all current playback
        sa.stop_all()
        
        if self.audio_data is None:
            print("audio not loaded.")
            return
        
        # if self.audio_segment is None:
        #     print("audio not loaded.")
        #     return
        
        if self.current_index < len(self.audio_files):
            audio_file = self.audio_files[self.current_index]
            self.text = self.get_text_ultimate()
            
            display_text = f"{os.path.basename(audio_file)} \n{self.text}"
            print(display_text)  # Debug statement
            self.text_display.setText(display_text)
            
            # Play the audio from start_ms, using wave
            start_frame = int(start_ms * self.sample_rate / 1000)
            self.audio_read.setpos(start_frame)
            audio_data = self.audio_read.readframes(self.num_frames - start_frame)
            self.play_obj = sa.play_buffer(audio_data, self.num_channels, self.bytes_per_sample, self.sample_rate)
            self.audio_position = start_ms
            self.timer.start()
            
            # # Play the audio from start_ms
            # audio = self.audio_segment[start_ms:]
            # self.play_obj = sa.play_buffer(audio.raw_data,
            #                                num_channels=audio.channels,
            #                                bytes_per_sample=audio.sample_width,  
            #                                sample_rate=audio.frame_rate)
            # self.audio_position = start_ms
            # self.timer.start()
        else:
            print("no more audio files.")
        
    def play_reference_audio(self, start_ms=0):
        """play reference audio function
        """
        # Stop all current playback
        sa.stop_all()
        
        if self.reference_audio_data is None:
            print("reference audio not loaded.")
            return
        
        # if self.reference_audio_segment is None:
        #     print("audio not loaded.")
        #     return
        
        if self.current_index < len(self.reference_audio_files):
            audio_file = self.reference_audio_files[self.current_index]
            display_text = f"{os.path.basename(audio_file)}"
            print(display_text)  # Debug statement
        
            # Play the audio from start_ms, using wave
            start_frame = int(start_ms * self.reference_audio_sample_rate / 1000)
            self.reference_audio_read.setpos(start_frame)
            audio_data = self.reference_audio_read.readframes(self.reference_audio_num_frames - start_frame)
            self.play_obj = sa.play_buffer(audio_data, self.reference_audio_num_channels, self.reference_audio_bytes_per_sample, self.reference_audio_sample_rate)
            self.audio_position = start_ms
            self.timer.start()
        
            # # Play the audio from start_frame
            # audio = self.reference_audio_segment[start_ms:]
            # self.play_obj = sa.play_buffer(audio.raw_data,
            #                                num_channels=audio.channels,
            #                                bytes_per_sample=audio.sample_width,  
            #                                sample_rate=audio.frame_rate)
            # self.audio_position = start_ms
            # self.timer.start()
        else:
            print("no more audio files.")
    
    def update_slider(self):
        """update the slider position per 10ms
        """
        if self.play_obj.is_playing():
            self.audio_position += 10
            if self.audio_position > self.audio_duration_ms:
                self.timer.stop()
                return
            self.progress_slider.setValue(self.audio_position)
            
    def seek_audio(self):
        """play audio from the seek time
        """
        seek_time = self.progress_slider.value()
        start_ms = seek_time
        self.play_audio(start_ms)

    def next_audio(self):
        """button for next audio
        """
        self.current_index += 1
        if self.current_index < len(self.audio_files):
            if self.current_index < len(self.texts):
                self.load_audio(self.audio_files[self.current_index])
            else:
                print("Text lines less than audio files.")
                self.current_index -= 1
        else:
            print("no more audio files.") 
            self.current_index -= 1

    def mark_result(self, result):
        """mark the result, if input two lines, the first line is the wrong word, the second line is the note. 
        If only one line, it is the note by default
        """
        if self.audio_files and 0 <= self.current_index < len(self.audio_files):
            current_audio = self.audio_files[self.current_index]
            note_content = self.note.toPlainText()
            # wrong_word = note_content.split('\n')[0] if '\n' in note_content else ''
            error_word = note_content.split('\n')[0] if '\n' in note_content else ''
            self.results.append({
                'file': os.path.basename(current_audio), 
                'text': self.text,
                'result': result,
                'error_word': error_word,
                'note': note_content
            })
        else:
            print("No audio files or index out of range")
            return
        self.current_index += 1
        if self.current_index < len(self.audio_files):
            audio_file = self.audio_files[self.current_index]
            self.load_audio(audio_file)
        else:
            print("no more audio files.") 
            self.current_index -= 1

    def replay_audio(self):
        self.play_audio()

    def save_and_summary(self):
        """save the results to a text file and an excel file, and calculate the statistics
        """
        folder = args.audio_folder
        folder_name = os.path.basename(folder)
        # add statistics to the text file
        with open(f"results_{folder_name}.txt", "a", encoding='utf-8') as file:
            for result in self.results:
                file.write(f"{result['file']}:{result['result']}\t{result['error_word']}\t{result['note']}\n{result['text']}\n\n")
        with open(f"results_{folder_name}.txt", "r", encoding='utf-8') as file:
            tp_count, tn_count, fp_count, fn_count, good_count, bad_count = 0, 0, 0, 0, 0, 0
            for line in file:
                if line.startswith('o') and 'TP\t' in line:
                    tp_count += 1
                elif line.startswith('o') and 'TN\t' in line:
                    tn_count += 1
                elif line.startswith('o') and 'FP\t' in line:
                    fp_count += 1
                elif line.startswith('o') and 'FN\t' in line:
                    fn_count += 1
                elif line.startswith('o') and 'T\t' in line:
                    good_count += 1
                elif line.startswith('o') and 'F\t' in line:
                    bad_count += 1
        recall = tp_count / (tp_count + fn_count) * 100 if (tp_count + fn_count) > 0 else 0
        recall = round(recall, 1)
        precision = tp_count / (tp_count + fp_count) * 100 if (tp_count + fp_count) > 0 else 0
        precision = round(precision, 1)
        with open(f"results_{folder_name}.txt", "a", encoding='utf-8') as file:
            file.write(f"\nTruePositive: {tp_count}\nTrueNegative: {tn_count}\nFalsePositive: {fp_count}\nFalseNegative: {fn_count}\n")
            file.write(f"Recall: (TP/(TP + FN))\t{recall}%\nPrecision: (TP/(TP + FP))\t{precision}%\n")
            file.write(f"Good: {good_count}\nBad: {bad_count}\n")

        # save results to excel file
        import pandas as pd
        if not os.path.exists(f"results_{folder_name}.xlsx"):
            with pd.ExcelWriter(f"results_{folder_name}.xlsx", mode='w') as writer:
                df = pd.DataFrame(columns=['file', 'text', 'result', 'error_word', 'note'])
                df.to_excel(writer, index=False, sheet_name='Results')   
        with pd.ExcelWriter(f"results_{folder_name}.xlsx", mode='a', if_sheet_exists='overlay') as writer:
            if os.path.exists(f"results_{folder_name}.xlsx"):
                existing_df = pd.read_excel(f"results_{folder_name}.xlsx", sheet_name='Results')
                df = pd.concat([existing_df, pd.DataFrame(self.results)], ignore_index=True)
            else:
                df = pd.DataFrame(self.results)
            df.to_excel(writer, index=False, sheet_name='Results')
            # add statistics
            stats_df = pd.DataFrame({
                'Metric': ['TruePositive', 'TrueNegative', 'FalsePositive', 'FalseNegative', 'Recall', 'Precision'],
                'Value': [tp_count, tn_count, fp_count, fn_count, recall, precision]
            })
            stats_df.to_excel(writer, index=False, sheet_name='Statistics')
        print("done")        
        print(f"TruePositive: {tp_count}\nTrueNegative: {tn_count}\nFalsePositive: {fp_count}\nFalseNegative: {fn_count}")
        print(f"Recall: {recall}%\nPrecision: {precision}%")
        print(f"Good: {good_count}\nBad: {bad_count}")
        self.results = []
        
    def save_progress(self):
        """save current progress
        """
        folder = args.audio_folder
        folder_name = os.path.basename(folder)
        # save results to text file
        with open(f"results_{folder_name}.txt", "a", encoding='utf-8') as file:
            for result in self.results:
                file.write(f"{result['file']}:{result['result']}\t{result['error_word']}\t{result['note']}\n{result['text']}\n\n")
                
        # save results to excel file
        import pandas as pd
        if not os.path.exists(f"results_{folder_name}.xlsx"):
            with pd.ExcelWriter(f"results_{folder_name}.xlsx", mode='w') as writer:
                df = pd.DataFrame(columns=['file', 'text', 'result', 'error_word', 'note'])
                df.to_excel(writer, index=False, sheet_name='Results')
        with pd.ExcelWriter(f"results_{folder_name}.xlsx", mode='a', if_sheet_exists='overlay') as writer:
            if os.path.exists(f"results_{folder_name}.xlsx"):
                existing_df = pd.read_excel(f"results_{folder_name}.xlsx", sheet_name='Results')
                df = pd.concat([existing_df, pd.DataFrame(self.results)], ignore_index=True)
            else:
                df = pd.DataFrame(self.results)
            df.to_excel(writer, index=False, sheet_name='Results')
        
        self.results = []

    def on_item_clicked(self, item):
        """handle audio list click event
        """
        filename = item.text()
        for file in self.audio_files:
            if os.path.basename(file) == filename:
                # jump to the selected audio file
                self.current_index = self.audio_files.index(file)
                self.load_audio(file)
                break
        else:
            print(f"File '{filename}' not found in audio files.")
            
    def switch_layout(self):
        """switch the layout between two button layouts and four button layouts
        """
        if self.TP_button.isVisible():
            self.TP_button.hide()
            self.TN_button.hide()
            self.FP_button.hide()
            self.FN_button.hide()
            self.TP_button2.show()
            self.TN_button2.show()
        else:
            self.TP_button.show()
            self.TN_button.show()
            self.FP_button.show()
            self.FN_button.show()
            self.TP_button2.hide()
            self.TN_button2.hide()


def main():
    app = QApplication(sys.argv)
    window = PyqtEvaluationTool()
    window.load_files(args.audio_folder, args.text_file, args.reference_audio_folder)    
    window.show()
    window.switch_layout()
    sys.exit(app.exec_())




if __name__ == "__main__":
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('--result_folder', type=str)
    parser.add_argument('--process_num', type=int, default=1)
    args = parser.parse_args()
    
    # change for the test data
    args.audio_folder = R"audio_folder"     # Your_audio_folder
    
    args.reference_audio_folder = R"reference_audio_folder"     # Your_reference_audio_folder
    
    args.text_file = R"test.txt"
    
    
    main()