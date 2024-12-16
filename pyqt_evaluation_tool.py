import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QTextEdit, QLabel, \
                            QVBoxLayout, QWidget, QTextEdit, QHBoxLayout, QSlider, QListWidget
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtCore import Qt
import simpleaudio as sa
from pydub import AudioSegment


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
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
        self.setWindowTitle("PyQt 音频听审工具")
        self.setup_ui()
        self.initialize_variables()
        self.setup_timer()
        
    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.setInterval(10)  # 100fps?
        self.timer.timeout.connect(self.update_slider)
        
    def initialize_variables(self):
        self.audio_files = []
        self.current_index = 0
        self.audio_thread = None
        self.results = []  # 存储结果的列表
        self.audio_segment = None
        self.play_obj = None
        self.frame_rate = None
        self.num_frames = None
        self.texts = []
        self.audio_position = 0
        self.audio_duration_ms = 0
        
    def setup_ui(self):
        # 设置深色主题
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Microsoft YaHei UI;
                font-weight: bold;
            }
            QLabel {
                font-size: 12pt;
                font-weight: bold;
                font-family: Microsoft YaHei UI;
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
        
        # 获取屏幕大小并将窗口放在屏幕中央
        desktop = QApplication.desktop()
        self.setGeometry(
            desktop.width() // 4 - 500,
            desktop.height() // 2 - 400,
            1080,
            800
        )
        
        # 创建主布局
        main_layout = QHBoxLayout()
        
        # 左侧列表控件
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("font-size: 11pt;")
        self.list_widget.itemClicked.connect(self.on_item_clicked)

        # 右侧的布局
        right_layout = QVBoxLayout()
        
        # 创建layout，左边放置文本显示框右边放置切换布局按钮
        top_layout = QHBoxLayout()
        text_label = QLabel("文本：", self)
        text_label.setStyleSheet("font-size: 12pt;")
        top_layout.addWidget(text_label)
        
        self.switch_button = QPushButton("切换布局", self)
        self.switch_button.setStyleSheet("font-size: 12pt; background-color: #009478;")
        self.switch_button.setFixedWidth(80)
        self.switch_button.clicked.connect(lambda: self.switch_layout())
        top_layout.addWidget(self.switch_button)
        
        right_layout.addLayout(top_layout)
        
        # 文本显示框
        self.text_display = QTextEdit(self)
        self.text_display.setReadOnly(True)
        self.text_display.setStyleSheet("font-size: 16pt;")
        right_layout.addWidget(self.text_display)
        
        # 创建layout，左边放置笔记标签右边放一个按钮‘播放参考音频’
        reference_layout = QHBoxLayout()
        note_label = QLabel("笔记：", self)
        note_label.setStyleSheet("font-size: 12pt;")
        reference_layout.addWidget(note_label)
        
        self.replay_button = QPushButton("重听", self)
        self.replay_button.setFixedHeight(40)  # 高度加倍
        self.replay_button.setStyleSheet("font-size: 16px; background-color: #008fb8;")
        self.replay_button.clicked.connect(self.replay_audio)
        reference_layout.addWidget(self.replay_button)
        
        self.play_reference_button = QPushButton("播放参考音频", self)
        self.play_reference_button.setStyleSheet("font-size: 12pt; background-color: #005bbd;")
        self.play_reference_button.setFixedHeight(40)
        self.play_reference_button.clicked.connect(lambda: self.load_reference_audio(self.reference_audio_files[self.current_index]))
        reference_layout.addWidget(self.play_reference_button)
        
        right_layout.addLayout(reference_layout)
        
        # 笔记框
        self.note = QTextEdit(self)
        self.note.setFixedHeight(100)
        self.note.setStyleSheet("font-size: 14pt;")
        right_layout.addWidget(self.note)
        
        # 进度条+重听按钮
        progressbar_layout = QHBoxLayout()
        self.progress_slider = ClickableSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderPressed.connect(self.seek_audio)
        progressbar_layout.addWidget(self.progress_slider)        
        
        right_layout.addLayout(progressbar_layout)
        
        # 下一个音频按钮
        self.next_button = QPushButton("下一个", self)
        self.next_button.setFixedHeight(40)
        self.next_button.setStyleSheet("font-size: 16px; color: black; background-color: #cccccc;")
        self.next_button.clicked.connect(lambda: self.next_audio())
        right_layout.addWidget(self.next_button)

        # 创建水平布局用于放置正确和错误按钮
        button_layout = QHBoxLayout()
        self.TP_button = QPushButton("读对识别为对", self)
        self.TP_button.setFixedHeight(100)  # 增加高度
        self.TP_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #007509; 
                """)
        self.TP_button.clicked.connect(lambda: self.mark_result("TP"))
        button_layout.addWidget(self.TP_button)
        
        self.TN_button = QPushButton("读错识别为错", self)
        self.TN_button.setFixedHeight(100)  # 增加高度
        self.TN_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #00870a; 
                """)
        self.TN_button.clicked.connect(lambda: self.mark_result("TN"))
        button_layout.addWidget(self.TN_button)
                
        self.FP_button = QPushButton("未识别", self)
        self.FP_button.setFixedHeight(100)
        self.FP_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #870100; 
                """)
        self.FP_button.clicked.connect(lambda: self.mark_result("FP"))
        button_layout.addWidget(self.FP_button)

        self.FN_button = QPushButton("读对识别错", self)
        self.FN_button.setFixedHeight(100)
        self.FN_button.setStyleSheet("""
                font-size: 22px; 
                font-weight: bold; 
                background-color: #750100; 
                """)
        self.FN_button.clicked.connect(lambda: self.mark_result("FN"))
        button_layout.addWidget(self.FN_button)
        
        right_layout.addLayout(button_layout)
        
        # 创建用于替换的水平布局用于放置正确和错误按钮
        button_layout2 = QHBoxLayout()
        self.TP_button2 = QPushButton("Good", self)
        self.TP_button2.setFixedHeight(100)  # 增加高度
        self.TP_button2.setStyleSheet("""
                font-size: 22px;
                font-weight: bold;
                background-color: #007509;
                """)
        self.TP_button2.clicked.connect(lambda: self.mark_result("T"))
        button_layout2.addWidget(self.TP_button2)
        
        self.TN_button2 = QPushButton("Bad", self)
        self.TN_button2.setFixedHeight(100)  # 增加高度
        self.TN_button2.setStyleSheet("""
                font-size: 22px;
                font-weight: bold;
                background-color: #870100;
                """)
        self.TN_button2.clicked.connect(lambda: self.mark_result("F"))
        button_layout2.addWidget(self.TN_button2)
        
        right_layout.addLayout(button_layout2)
        
        # 创建水平布局用于放置保存和退出按钮
        save_exit_layout = QHBoxLayout()
        self.save_button = QPushButton("保存", self)
        self.save_button.setStyleSheet("font-size: 16px; background-color: #b34500")
        self.save_button.clicked.connect(self.save_progress)
        save_exit_layout.addWidget(self.save_button)
        
        # 创建退出按钮
        self.exit_button = QPushButton("保存并退出", self)
        self.exit_button.setStyleSheet("font-size: 16px; background-color: #7d2547;")
        self.exit_button.clicked.connect(self.save_and_exit)
        save_exit_layout.addWidget(self.exit_button)
        
        right_layout.addLayout(save_exit_layout)

        # 将列表控件和右侧布局添加到主布局
        main_layout.addWidget(self.list_widget, 1)
        main_layout.addLayout(right_layout, 5)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def load_files(self, audio_folder, text_file, reference_audio_folder=None):
        self.switch_layout()
        self.texts = []
        if os.path.exists(text_file):
            with open(text_file, 'r', encoding='utf-8') as f:
                self.texts = f.read().splitlines()
        else:
            print(f"未找到文本文件 {text_file}")
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
                self.current_index = 0      # current_index 从 0 开始
                self.load_audio(self.audio_files[self.current_index])
            except ValueError:
                print("Index initialization error.")
                self.current_index = 0
        else:
            print(f"未找到音频文件夹 {audio_folder}")
            self.audio_files = []
            
        if reference_audio_folder and os.path.exists(reference_audio_folder):
            self.reference_audio_files = [
                os.path.join(reference_audio_folder, f) 
                for f in os.listdir(reference_audio_folder) 
                if f.endswith('.wav')
            ]
        
    def get_text(self):
        """根据 self.current_index 返回对应的参考文本。假设文本从第4行开始，每个音频文件的文本以空行分隔。"""
        if not self.texts or self.current_index < 0:
            return "没有可用的文本。"

        # 从第4行开始（索引3）
        current_line = 3
        audio_count = 0
        text_block = []

        while current_line < len(self.texts):
            line = self.texts[current_line].strip()
            if line.endswith('.wav'):
                if audio_count == self.current_index:
                    # 收集此音频对应的文本
                    current_line += 1
                    while current_line < len(self.texts):
                        text_line = self.texts[current_line].strip()
                        if text_line == '':
                            break
                        text_block.append(text_line)
                        current_line += 1
                    break
                audio_count += 1
            current_line += 1

        return '\n'.join(text_block) if text_block else "没有对应的文本内容。"

    def get_text_pattern2(self, n=4):
        """根据index返回对应的参考文本。文本从第1行开始，每n行为一个音频文件的文本。"""
        if not self.texts or self.current_index < 0:
            return "没有可用的文本。"
        
        # 从第1行开始（索引0）
        current_line = 0
        audio_count = 0
        text_block = []
        
        while current_line < len(self.texts):
            line = self.texts[current_line].strip()
            if line.endswith('%'):
                if audio_count == self.current_index:
                    # 收集此音频对应的文本
                    current_line += 1
                    for i in range(n-1):
                        text_line = self.texts[current_line].strip()
                        print(text_line)
                        text_block.append(text_line)
                        current_line += 1
                    break
                audio_count += 1
            current_line += 1
            
        return '\n'.join(text_block) if text_block else "没有对应的文本内容。"
    
    def load_audio(self, file_path):
        # Load the audio file using pydub
        self.audio_segment = AudioSegment.from_wav(file_path)
        self.audio_duration_ms = len(self.audio_segment)
        self.progress_slider.setRange(0, int(self.audio_duration_ms))
        # 清空笔记框
        self.note.clear()
        # Start playing from the beginning
        self.play_audio(0)
    
    def load_reference_audio(self, file_path):
        # Load the audio file using pydub
        self.reference_audio_segment = AudioSegment.from_wav(file_path)
        self.reference_audio_duration_ms = len(self.reference_audio_segment)
        self.play_reference_audio(0)
    
    def play_audio(self, start_ms=0):
        # Stop all current playback
        sa.stop_all()
        
        if self.audio_segment is None:
            print("音频未加载。")
            return
        
        if self.current_index < len(self.audio_files):
            audio_file = self.audio_files[self.current_index]
            self.text = self.get_text()
            
            display_text = f"{os.path.basename(audio_file)} \n{self.text}"
            print(display_text)  # Debug statement
            self.text_display.setText(display_text)
            
            # Play the audio from start_frame
            audio = self.audio_segment[start_ms:]
            self.play_obj = sa.play_buffer(audio.raw_data,
                                           num_channels=audio.channels,
                                           bytes_per_sample=audio.sample_width,  
                                           sample_rate=audio.frame_rate)
            self.audio_position = start_ms
            self.timer.start()
        else:
            print("没有更多音频文件。")
        
    def play_reference_audio(self, start_ms=0):
        # Stop all current playback
        sa.stop_all()
        
        if self.reference_audio_segment is None:
            print("音频未加载。")
            return
        
        if self.current_index < len(self.reference_audio_files):
            audio_file = self.reference_audio_files[self.current_index]
            display_text = f"{os.path.basename(audio_file)}"
            print(display_text)  # Debug statement
        
            # Play the audio from start_frame
            audio = self.reference_audio_segment[start_ms:]
            self.play_obj = sa.play_buffer(audio.raw_data,
                                           num_channels=audio.channels,
                                           bytes_per_sample=audio.sample_width,  
                                           sample_rate=audio.frame_rate)
            self.audio_position = start_ms
            self.timer.start()
        else:
            print("没有更多音频文件。")
    
    def update_slider(self):
        if self.play_obj.is_playing():
            self.audio_position += 10
            if self.audio_position > self.audio_duration_ms:
                self.timer.stop()
                return
            self.progress_slider.setValue(self.audio_position)
            
    def seek_audio(self):
        seek_time = self.progress_slider.value()
        start_ms = seek_time
        self.play_audio(start_ms)

    def next_audio(self):
        self.current_index += 1
        if self.current_index < len(self.audio_files):
            audio_file = self.audio_files[self.current_index]
            self.load_audio(audio_file)
        else:
            print("没有更多音频文件。") 
            self.current_index -= 1

    def mark_result(self, result):
        current_audio = self.audio_files[self.current_index]
        note_content = self.note.toPlainText()
        self.results.append({
            'file': os.path.basename(current_audio), 
            '内容': self.text,
            '结果': result,
            '笔记': note_content
        })
        self.current_index += 1
        if self.current_index < len(self.audio_files):
            audio_file = self.audio_files[self.current_index]
            self.load_audio(audio_file)
        else:
            print("没有更多音频文件。") 
            self.current_index -= 1

    def replay_audio(self):
        self.play_audio()

    def save_and_exit(self):
        # 保存结果到文本文件
        with open("results.txt", "a", encoding='utf-8') as file:
            for result in self.results:
                file.write(f"{result['file']}:{result['结果']}\t{result['笔记']}\n{result['内容']}\n\n")
        self.close()
        
    def save_progress(self):
        # 保存结果到文本文件
        with open("results.txt", "a", encoding='utf-8') as file:
            for result in self.results:
                file.write(f"{result['file']}:{result['结果']}\t{result['笔记']}\n{result['内容']}\n\n")
        self.results = []

    def on_item_clicked(self, item):
        filename = item.text()
        for file in self.audio_files:
            if os.path.basename(file) == filename:
                # 跳转到选中的音频
                self.current_index = self.audio_files.index(file)
                self.load_audio(file)
                break
            
    def switch_layout(self):
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

    audio_folder = R"Data\Output\Dragon\多音字104句1181"
    text_file = R"Drgn_vs_XX_多音字104句1181_104_phoneme.txt"
    reference_audio_folder = R"Data\Output\Dragon\多音字104句new"
    
    # 调用 load_files 并传递参数
    window.load_files(audio_folder, text_file, reference_audio_folder)    
    window.show()
    sys.exit(app.exec_())




if __name__ == "__main__":
    main()