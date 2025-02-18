import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGridLayout, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
import time
import Quartz
import os
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import requests

class ClickerThread(QThread):
    """自动点击线程类，处理实际的点击操作"""
    update_status = pyqtSignal(str, int)  # 状态更新信号，发送点击状态和次数

    def __init__(self, interval, x, y):
        """
        初始化点击线程
        Args:
            interval: 点击间隔时间（秒）
            x: 点击位置的X坐标，None表示使用当前鼠标位置
            y: 点击位置的Y坐标，None表示使用当前鼠标位置
        """
        QThread.__init__(self)
        self.interval = interval
        self.x = x
        self.y = y
        self.running = True
        self.click_count = 0

    def run(self):
        while self.running:
            self.perform_click()
            self.click_count += 1
            time.sleep(self.interval)
            self.update_status.emit("正在点击", self.click_count)

    def stop(self):
        self.running = False

    def perform_click(self):
        """执行单次点击操作"""
        # 确定点击位置：使用指定坐标或当前鼠标位置
        if self.x is not None and self.y is not None:
            point = Quartz.CGPoint(self.x, self.y)
        else:
            current_position = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
            point = Quartz.CGPoint(current_position.x, current_position.y)

        # 创建鼠标按下和释放事件
        mouse_down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, point, Quartz.kCGMouseButtonLeft)
        mouse_up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, point, Quartz.kCGMouseButtonLeft)

        # 发送点击事件
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, mouse_down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, mouse_up)

class AutoClickerApp(QWidget):
    """自动点击器的主应用程序类"""
    
    def __init__(self):
        """初始化应用程序界面和功能"""
        super().__init__()
        self.user = None
        self.initUI()
        self.clicker_thread = None
        
        # 设置鼠标位置更新定时器
        self.mouse_pos_timer = QTimer(self)
        self.mouse_pos_timer.timeout.connect(self.update_mouse_position)
        self.mouse_pos_timer.start(100)  # 每100ms更新一次鼠标位置
        
        # 初始化试用期检查
        self.check_trial_period()
        self.start_time = datetime.now()
        
        # 设置试用期更新定时器
        self.trial_timer = QTimer(self)
        self.trial_timer.timeout.connect(self.update_trial_time)
        self.trial_timer.start(60000)  # 每分钟更新一次试用时间

    def initUI(self):
        """初始化用户界面"""
        layout = QVBoxLayout()

        # 添加用户注册和激活控件
        self.email_input = QLineEdit(self)
        self.email_input.setPlaceholderText("输入邮箱")
        layout.addWidget(self.email_input)

        self.register_button = QPushButton('注册', self)
        self.register_button.clicked.connect(self.register_user)
        layout.addWidget(self.register_button)

        self.activate_button = QPushButton('激活账号', self)
        self.activate_button.clicked.connect(self.activate_account)
        layout.addWidget(self.activate_button)

        self.payment_button = QPushButton('购买完整版', self)
        self.payment_button.clicked.connect(self.initiate_payment)
        layout.addWidget(self.payment_button)

        grid_layout = QGridLayout()
        layout.addLayout(grid_layout)

        label = QLabel('时间间隔 (ms):')
        grid_layout.addWidget(label, 0, 0)
        grid_layout.setAlignment(label, Qt.AlignmentFlag.AlignLeft)

        self.interval_input = QLineEdit('1000')
        grid_layout.addWidget(self.interval_input, 0, 1)

        grid_layout.addWidget(QLabel('点击位置 X:'), 1, 0)
        self.x_input = QLineEdit()
        grid_layout.addWidget(self.x_input, 1, 1)

        grid_layout.addWidget(QLabel('点击位置 Y:'), 2, 0)
        self.y_input = QLineEdit()
        grid_layout.addWidget(self.y_input, 2, 1)

        self.toggle_button = QPushButton('开始')
        self.toggle_button.clicked.connect(self.toggle_clicking)
        grid_layout.addWidget(self.toggle_button, 3, 0, 1, 2)

        self.status_label = QLabel('状态: 未开始')
        layout.addWidget(self.status_label)

        self.click_count_label = QLabel('点击次数: 0')
        layout.addWidget(self.click_count_label)

        self.mouse_pos_label = QLabel('当前鼠标位置: (0, 0)')
        layout.addWidget(self.mouse_pos_label)

        self.setLayout(layout)

    def toggle_clicking(self):
        """切换自动点击的开始/停止状态"""
        if self.clicker_thread is None or not self.clicker_thread.isRunning():
            try:
                # 获取并验证点击间隔时间
                interval_ms = int(self.interval_input.text())
                interval = interval_ms / 1000.0
                if interval <= 0:
                    raise ValueError("间隔时间必须大于0")
                
                # 获取点击位置坐标
                x = int(self.x_input.text()) if self.x_input.text() else None
                y = int(self.y_input.text()) if self.y_input.text() else None

                # 创建并启动点击线程
                self.clicker_thread = ClickerThread(interval, x, y)
                self.clicker_thread.update_status.connect(self.update_status)
                self.clicker_thread.start()
                self.toggle_button.setText('暂停')
                self.status_label.setText('状态: 正在点击')
            except ValueError as e:
                self.status_label.setText(f'错误: {str(e)}')
        else:
            # 停止点击线程
            self.clicker_thread.stop()
            self.clicker_thread.wait()
            self.toggle_button.setText('开始')
            self.status_label.setText('状态: 已暂停')

    def update_status(self, status, click_count):
        self.status_label.setText(f'状态: {status}')
        self.click_count_label.setText(f'点击次数: {click_count}')

    def update_mouse_position(self):
        current_position = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        self.mouse_pos_label.setText(f'当前鼠标位置: ({int(current_position.x)}, {int(current_position.y)})')

    def check_trial_period(self):
        """检查试用期状态"""
        config_path = os.path.expanduser('~/.autoclicker_config')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            total_usage = config.get('total_usage', 0)
            if total_usage >= 30 * 60:  # 30分钟试用期
                self.disable_app("试用期已结束")
                return
        else:
            # 创建新的配置文件
            config = {'total_usage': 0}
            with open(config_path, 'w') as f:
                json.dump(config, f)

    def update_trial_time(self):
        """更新试用时间"""
        config_path = os.path.expanduser('~/.autoclicker_config')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # 计算已使用时间
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        config['total_usage'] += elapsed_time
        
        # 保存更新后的使用时间
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        self.start_time = datetime.now()
        
        # 检查是否超过试用期限
        if config['total_usage'] >= 30 * 60:
            self.disable_app("试用期已结束")

    def disable_app(self, message):
        """禁用应用程序功能"""
        self.toggle_button.setEnabled(False)
        self.status_label.setText(f"状态: {message}")
        if self.clicker_thread and self.clicker_thread.isRunning():
            self.clicker_thread.stop()
            self.clicker_thread.wait()

    def register_user(self):
        email = self.email_input.text()
        if not email:
            QMessageBox.warning(self, '错误', '请输入有效的邮箱地址')
            return

        # 在这里添加用户到数据库的逻辑
        # 为简单起见，我们只是将用户信息保存到一个文件中
        user_data = {'email': email, 'activated': False, 'paid': False}
        with open('users.json', 'w') as f:
            json.dump(user_data, f)

        self.send_activation_email(email)
        QMessageBox.information(self, '注册成功', '请查看您的邮箱以激活账号')

    def send_activation_email(self, email):
        # 这里应该实现发送激活邮件的逻辑
        # 为了演示，我们只是打印一条消息
        print(f"激活邮件已送到 {email}")

    def activate_account(self):
        # 这里应该实现验证激活码的逻辑
        # 为了演示，我们只是将用户标记为已激活
        with open('users.json', 'r') as f:
            user_data = json.load(f)
        user_data['activated'] = True
        with open('users.json', 'w') as f:
            json.dump(user_data, f)
        QMessageBox.information(self, '激活成功', '您的账号已成功激活')

    def initiate_payment(self):
        # 这里应该实现跳转到Paddle支付页面的逻辑
        # 为了演示，我们只是打印一条消息
        print("跳转到Paddle支付页面")

    def check_user_status(self):
        if os.path.exists('users.json'):
            with open('users.json', 'r') as f:
                user_data = json.load(f)
            if user_data['activated'] and user_data['paid']:
                return True
        return False

    def run_autoclicker(self):
        if not self.check_user_status():
            QMessageBox.warning(self, '未授权', '请激活您的账号并购买完整版')
            return
        # ... 自动点击器的原有逻辑 ...

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AutoClickerApp()
    ex.show()
    sys.exit(app.exec())
