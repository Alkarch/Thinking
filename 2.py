import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Canvas
import fitz  # PyMuPDF
import requests
import json
import base64
from PIL import Image, ImageTk
import io
import os
import subprocess
import time
import threading
from fpdf import FPDF  # Добавляем для экспорта в PDF

class DrawingCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Проверка чертежей PDF")
        self.root.geometry("1200x800")  # Увеличили размер для preview
        
        # Инициализируем атрибуты
        self.ollama_url = "http://localhost:11434"
        self.is_ollama_running = False
        self.current_check_thread = None
        self.stop_check = False
        
        # Оптимизированные модели
        self.fast_models = [
            "llama2:3b", 
            "tinyllama", 
            "qwen:1.8b",
            "llama3:8b"
        ]
        
        self.vision_models = [
            "llava:7b",  
            "bakllava:7b", 
            "llava:13b"  
        ]
        
        self.create_widgets()
        
        self.root.after(1000, self.auto_check_ollama)
        
    def auto_check_ollama(self):
        if self.test_connection():
            self.status_label.config(text="Статус: Ollama подключен")
            self.is_ollama_running = True
            self.update_model_info()
        else:
            self.status_label.config(text="Статус: Ollama не запущен")
            self.is_ollama_running = False
    
    def test_connection(self):
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def create_widgets(self):
        # Заголовок
        title_label = tk.Label(self.root, text="Проверка чертежей на соответствие ГОСТ", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Фрейм для настроек
        settings_frame = tk.Frame(self.root)
        settings_frame.pack(pady=5)
        
        # Выбор модели (текстовые)
        tk.Label(settings_frame, text="Текстовая модель:").grid(row=0, column=0, padx=5)
        self.model_var = tk.StringVar(value="llama2:3b")
        model_menu = tk.OptionMenu(settings_frame, self.model_var, *self.fast_models)
        model_menu.grid(row=0, column=1, padx=5)
        
        # Выбор модели для vision
        tk.Label(settings_frame, text="Vision модель:").grid(row=1, column=0, padx=5)
        self.vision_model_var = tk.StringVar(value="llava:7b")
        vision_menu = tk.OptionMenu(settings_frame, self.vision_model_var, *self.vision_models)
        vision_menu.grid(row=1, column=1, padx=5)
        
        # Кнопка проверки подключения
        self.test_btn = tk.Button(settings_frame, text="Проверить подключение", 
                                 command=self.test_connection_ui)
        self.test_btn.grid(row=0, column=2, padx=10)
        
        # Кнопка остановки проверки
        self.stop_btn = tk.Button(settings_frame, text="Остановить проверку", 
                                 command=self.stop_checking,
                                 state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=3, padx=10)
        
        # Информация о моделях
        self.model_info = tk.Label(settings_frame, text="", fg="blue", font=("Arial", 8))
        self.model_info.grid(row=2, column=0, columnspan=4, pady=2)
        
        # Прогресс
        self.progress = tk.Label(self.root, text="", fg="green")
        self.progress.pack(pady=2)
        
        # Кнопка загрузки
        self.upload_btn = tk.Button(self.root, text="Загрузить PDF", 
                                   command=self.upload_pdf,
                                   font=("Arial", 12))
        self.upload_btn.pack(pady=5)
        
        # Preview область
        self.preview_frame = tk.Frame(self.root)
        self.preview_frame.pack(pady=5)
        
        tk.Label(self.preview_frame, text="Предпросмотр PDF:").pack()
        self.preview_canvas = Canvas(self.preview_frame, width=400, height=300, bg="white")
        self.preview_canvas.pack()
        
        # Кнопка проверки
        self.check_btn = tk.Button(self.root, text="Проверить чертеж (полная)", 
                                  command=self.check_drawing,
                                  font=("Arial", 12),
                                  state=tk.DISABLED)
        self.check_btn.pack(pady=5)
        
        # Быстрая проверка
        self.quick_check_btn = tk.Button(self.root, text="Быстрая проверка", 
                                        command=self.quick_check_drawing,
                                        font=("Arial", 10),
                                        state=tk.DISABLED,
                                        bg="lightgreen")
        self.quick_check_btn.pack(pady=2)
        
        # Кнопка экспорта
        self.export_btn = tk.Button(self.root, text="Сохранить отчет", 
                                   command=self.export_report,
                                   font=("Arial", 12),
                                   state=tk.DISABLED)
        self.export_btn.pack(pady=5)
        
        # Поле для вывода результатов
        self.result_text = scrolledtext.ScrolledText(self.root, 
                                                   height=20,
                                                   width=100,
                                                   font=("Arial", 10))
        self.result_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # Статус
        self.status_label = tk.Label(self.root, text="Статус: Проверка Ollama...")
        self.status_label.pack(pady=5)
        
        self.current_pdf_path = None
        self.analysis_result = ""  # Для хранения результатов для экспорта
    
    def test_connection_ui(self):
        if self.test_connection():
            self.status_label.config(text="Статус: Ollama подключен")
            self.is_ollama_running = True
            self.update_model_info()
            messagebox.showinfo("Успех", "Ollama подключен!")
        else:
            self.status_label.config(text="Статус: Ollama не доступен")
            self.is_ollama_running = False
            messagebox.showerror("Ошибка", "Ollama не доступен. Запустите сервис.")
    
    def update_model_info(self):
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    model_names = [model["name"] for model in models]
                    self.model_info.config(text=f"Модели: {', '.join(model_names[:5])}...")
                else:
                    self.model_info.config(text="Модели не установлены")
            else:
                self.model_info.config(text="Ошибка получения моделей")
        except:
            self.model_info.config(text="Не удалось получить модели")
    
    def stop_checking(self):
        self.stop_check = True
        if self.current_check_thread and self.current_check_thread.is_alive():
            self.status_label.config(text="Статус: Останавливаем проверку...")
            self.stop_btn.config(state=tk.DISABLED)
    
    def upload_pdf(self):
        file_path = filedialog.askopenfilename(
            title="Выберите PDF файл",
            filetypes=[("PDF files", "*.pdf")]
        )
        
        if file_path:
            self.current_pdf_path = file_path
            self.check_btn.config(state=tk.NORMAL)
            self.quick_check_btn.config(state=tk.NORMAL)
            self.export_btn.config(state=tk.DISABLED)  # Сброс экспорта
            self.status_label.config(text=f"Загружен: {os.path.basename(file_path)}")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"Файл загружен: {file_path}\n\n")
            self.display_pdf_preview(file_path)
    
    def display_pdf_preview(self, pdf_path):
        """Отображает предпросмотр первой страницы PDF"""
        try:
            doc = fitz.open(pdf_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=72)  # Низкое разрешение для preview
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img = img.resize((400, 300), Image.LANCZOS)  # Масштабируем
            self.preview_img = ImageTk.PhotoImage(img)  # Сохраняем ссылку
            self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_img)
            doc.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось отобразить preview: {str(e)}")
    
    def extract_text_from_pdf(self, pdf_path, max_pages=3):
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page_num in range(min(len(doc), max_pages)):
                page = doc.load_page(page_num)
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            return f"Ошибка извлечения текста: {str(e)}"
    
    def extract_images_from_pdf(self, pdf_path, max_pages=3):
        try:
            doc = fitz.open(pdf_path)
            base64_images = []
            for page_num in range(min(len(doc), max_pages)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                base64_img = base64.b64encode(buffered.getvalue()).decode('utf-8')
                base64_images.append(base64_img)
            doc.close()
            return base64_images
        except Exception as e:
            return f"Ошибка извлечения изображений: {str(e)}"
    
    def analyze_with_ollama_fast(self, text_content, base64_images=None):
        truncated_text = text_content[:1000] + "..." if len(text_content) > 1000 else text_content
        
        prompt = f"""
ТЫ: Эксперт ГОСТ. Проанализируй чертеж быстро, включая текст и графику.

КРИТЕРИИ:
- Основная надпись (наименование, код, подписи)
- Соответствие кода документа (СБ, ВО, ГЧ, МЧ)
- Обязательные реквизиты (масса, масштаб)
- Положение деталей: проверка размеров на полках линий-выносок, угловые размеры в зоне 30°, дополнительные стрелки для допусков
- Шероховатость: наличие знака √ в скобках
- Позиции фигур: наличие буквенных обозначений баз (A, B и т.д.), их соответствие в рамках

ТЕКСТ: {truncated_text}

Если есть изображение: опиши графику, проверь положение элементов, сравни с текстом.

Для каждой проблемы добавь ссылку на ГОСТ: 
- ГОСТ 2.308-2011: https://meganorm.ru/Data2/1/4293800/4293800222.pdf (допуски формы)
- ГОСТ 2.307-2011: https://meganorm.ru/Data2/1/4293800/4293800223.pdf (размеры)
- ГОСТ 2.309-73: https://www.ntcexpert.ru/documents/GOST_2.309.pdf (шероховатость)
- ГОСТ 2.104-2006: https://meganorm.ru/Data2/1/4293850/4293850184.pdf (основные надписи)

ФОРМАТ ОТВЕТА (ТОЧНО):

СООТВЕТСТВИЕ: [ДА/НЕТ]
ПРОБЛЕМЫ:
- [проблема 1] (Ссылка на ГОСТ: [ссылка])
- [проблема 2] 
РЕКОМЕНДАЦИИ:
- [рекомендация 1]

ТОЛЬКО РУССКИЙ ЯЗЫК. КРАТКО.
"""
        
        payload = {
            "model": self.vision_model_var.get() if base64_images else self.model_var.get(),
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.05,
                "num_predict": 300,
                "top_k": 20,
                "repeat_penalty": 1.1
            }
        }
        
        if base64_images:
            payload["images"] = base64_images
        
        try:
            response = requests.post(f"{self.ollama_url}/api/generate", 
                                   json=payload, timeout=60)
            
            if response.status_code == 200:
                return response.json().get("response", "Нет ответа")
            else:
                return f"Ошибка API: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return "Таймаут: модель не успела ответить за 60 секунд"
        except Exception as e:
            return f"Ошибка: {str(e)}"
    
    def analyze_with_ollama_standard(self, text_content, base64_images=None):
        truncated_text = text_content[:1800] + "..." if len(text_content) > 1800 else text_content
        
        prompt = f"""
ТЫ: Эксперт по технической документации и российским стандартам ГОСТ. Твоя задача - анализировать чертежи на соответствие ГОСТ, включая текст и графику (положение деталей, фигур, размеров).

АНАЛИЗИРУЙ этот чертеж и проверь соответствие ГОСТ по следующим критериям:

1. ОСНОВНАЯ НАДПИСЬ - наличие и правильность заполнения:
   - Наименование изделия
   - Обозначение документа (код: СБ, ВО, ГЧ, МЧ и т.д.)
   - Подписи (Разраб., Пров., Т.контр., Н.контр., Утв.)
   - Масса, масштаб, листы

2. КОД ДОКУМЕНТА - соответствие наименованию:
   - СБ = Сборочный чертеж
   - ВО = Чертеж общего вида  
   - ГЧ = Габаритный чертеж
   - МЧ = Монтажный чертеж

3. ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
   - Расположение над основной надписью
   - Ширина не более 185 мм

4. ОБОЗНАЧЕНИЯ И СИМВОЛЫ:
   - Буквенные обозначения в технических требованиях
   - Символы *, **, *** 
   - Знак √ в скобках для шероховатости

5. ГРАФИКА И ПОЛОЖЕНИЕ:
   - Простановка размеров на полке линии-выноски (в зоне 30°)
   - Угловые размеры в зоне 30°
   - Дополнительные стрелки для допусков формы (ГОСТ 2.308)
   - Соответствие буквенных обозначений баз в рамках
   - Положение фигур, деталей: сравни с текстом, выяви несоответствия (например, Ra на поверхностях)

ТЕКСТ ЧЕРТЕЖА ДЛЯ АНАЛИЗА:
{truncated_text}

Если есть изображение: опиши видимые элементы, проверь позиции, сравни с требованиями ГОСТ.

Для каждой проблемы добавь ссылку на ГОСТ: 
- ГОСТ 2.308-2011: https://meganorm.ru/Data2/1/4293800/4293800222.pdf (допуски формы)
- ГОСТ 2.307-2011: https://meganorm.ru/Data2/1/4293800/4293800223.pdf (размеры)
- ГОСТ 2.309-73: https://www.ntcexpert.ru/documents/GOST_2.309.pdf (шероховатость)
- ГОСТ 2.104-2006: https://meganorm.ru/Data2/1/4293850/4293850184.pdf (основные надписи)

ФОРМАТ ОТВЕТА (СТРОГО ПРИДЕРЖИВАЙСЯ ЭТОГО ФОРМАТА):

СООТВЕТСТВИЕ: [ДА/НЕТ]
ОБЩИЙ ВЫВОД: [1-2 предложения]

ДЕТАЛЬНЫЙ АНАЛИЗ:
1. Основная надпись: [СООТВЕТСТВУЕТ/НЕ СООТВЕТСТВУЕТ] - [причина] (Ссылка на ГОСТ: [ссылка])
2. Код документа: [СООТВЕТСТВУЕТ/НЕ СООТВЕТСТВУЕТ] - [причина]  
3. Подписи: [СООТВЕТСТВУЕТ/НЕ СООТВЕТСТВУЕТ] - [причина]
4. Технические требования: [СООТВЕТСТВУЕТ/НЕ СООТВЕТСТВУЕТ] - [причина]
5. Обозначения: [СООТВЕТСТВУЕТ/НЕ СООТВЕТСТВУЕТ] - [причина]
6. Графика и положение: [СООТВЕТСТВУЕТ/НЕ СООТВЕТСТВУЕТ] - [причина, включая описание позиций] (Ссылка на ГОСТ: [ссылка])

РЕКОМЕНДАЦИИ:
- [конкретная рекомендация 1]
- [конкретная рекомендация 2]

НЕ ИЗМЕНЯЙ ФОРМАТ ОТВЕТА. ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.
"""
        
        payload = {
            "model": self.vision_model_var.get() if base64_images else self.model_var.get(),
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 600,
                "top_p": 0.8,
                "repeat_penalty": 1.2
            }
        }
        
        if base64_images:
            payload["images"] = base64_images
        
        try:
            response = requests.post(f"{self.ollama_url}/api/generate", 
                                   json=payload, timeout=(30, 120))
            
            if self.stop_check:
                return "Проверка прервана пользователем"
            
            if response.status_code == 200:
                return response.json().get("response", "Нет ответа от модели")
            else:
                return f"Ошибка API: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return self.fallback_analysis(text_content)
        except Exception as e:
            return f"Ошибка соединения: {str(e)}"

    def fallback_analysis(self, text_content):
        self.root.after(0, self._update_progress, "Таймаут! Используем упрощенный анализ...")
        
        checks = {
            "Основная надпись": ["разраб", "пров", "лист", "листов", "масса", "масштаб"],
            "Код документа": ["сб", "во", "гч", "мч", "рнат"],
            "Подписи": ["разраб", "пров", "т.контр", "утв"],
            "Графика": ["ra", "поверхность", "размер", "стрелка"]
        }
        
        result = "УПРОЩЕННЫЙ АНАЛИЗ (после таймаута):\n\n"
        text_lower = text_content.lower()
        
        for check_name, keywords in checks.items():
            found = any(keyword in text_lower for keyword in keywords)
            status = "✓ ЕСТЬ" if found else "✗ НЕТ"
            result += f"{check_name}: {status}\n"
        
        result += "\nПримечание: Полный анализ не удался из-за таймаута нейросети. Графика не проанализирована."
        return result

    def check_drawing(self):
        if not self.current_pdf_path:
            messagebox.showerror("Ошибка", "Сначала загрузите PDF файл")
            return
        
        if not self.is_ollama_running:
            messagebox.showerror("Ошибка", "Ollama не запущен")
            return
            
        self.stop_check = False
        self.current_check_thread = threading.Thread(target=self._check_drawing_thread, 
                                                   args=(self.analyze_with_ollama_standard, True),
                                                   daemon=True)
        self.current_check_thread.start()
    
    def quick_check_drawing(self):
        if not self.current_pdf_path:
            messagebox.showerror("Ошибка", "Сначала загрузите PDF файл")
            return
        
        if not self.is_ollama_running:
            messagebox.showerror("Ошибка", "Ollama не запущен")
            return
            
        self.stop_check = False
        self.current_check_thread = threading.Thread(target=self._check_drawing_thread, 
                                                   args=(self.analyze_with_ollama_fast, False),
                                                   daemon=True)
        self.current_check_thread.start()

    def _check_drawing_thread(self, analysis_function, include_graphics=False):
        self.root.after(0, self._update_ui_check_started)
        
        try:
            text_content = self.extract_text_from_pdf(self.current_pdf_path)
            
            if self.stop_check:
                return
                
            self.root.after(0, self._update_progress, f"Текст извлечен: {len(text_content)} символов")
            
            base64_images = None
            if include_graphics:
                self.root.after(0, self._update_progress, "Извлекаем графику...")
                base64_images = self.extract_images_from_pdf(self.current_pdf_path)
                if isinstance(base64_images, str):
                    self.root.after(0, self._display_error, base64_images)
                    return
                self.root.after(0, self._update_progress, f"Извлечено {len(base64_images)} изображений")
            
            if self.stop_check:
                return
                
            ai_result = analysis_function(text_content, base64_images)
            
            if self.stop_check:
                return
                
            self.analysis_result = ai_result  # Сохраняем для экспорта
            self.root.after(0, self._display_results, ai_result)
            
        except Exception as e:
            self.root.after(0, self._display_error, str(e))
    
    def _update_ui_check_started(self):
        self.status_label.config(text="Статус: Идет проверка...")
        self.check_btn.config(state=tk.DISABLED)
        self.quick_check_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.export_btn.config(state=tk.DISABLED)
        self.result_text.insert(tk.END, "Начинаем проверку...\n")
    
    def _update_progress(self, message):
        self.progress.config(text=message)
        self.result_text.insert(tk.END, f"{message}\n")
        self.root.update()
    
    def _display_results(self, result):
        self.result_text.insert(tk.END, "\n" + "="*60 + "\n")
        self.result_text.insert(tk.END, "РЕЗУЛЬТАТЫ ПРОВЕРКИ:\n")
        self.result_text.insert(tk.END, "="*60 + "\n\n")
        self.result_text.insert(tk.END, result)
        
        self._reset_ui_after_check()
        self.export_btn.config(state=tk.NORMAL)  # Активируем экспорт
    
    def _display_error(self, error):
        messagebox.showerror("Ошибка", f"Произошла ошибка: {error}")
        self._reset_ui_after_check()
    
    def _reset_ui_after_check(self):
        self.status_label.config(text="Статус: Проверка завершена")
        self.check_btn.config(state=tk.NORMAL)
        self.quick_check_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.config(text="")
        self.stop_check = False
    
    def export_report(self):
        """Экспортирует отчет в PDF"""
        if not self.analysis_result:
            messagebox.showerror("Ошибка", "Нет результатов для экспорта")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Сохранить отчет"
        )
        
        if file_path:
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)  # Для русского текста (нужно скачать шрифт)
                pdf.set_font("DejaVu", size=12)
                pdf.multi_cell(0, 10, self.analysis_result.encode('latin-1', 'replace').decode('latin-1'))  # Простая обработка
                pdf.output(file_path)
                messagebox.showinfo("Успех", f"Отчет сохранен: {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {str(e)}")
                # Примечание: Скачайте DejaVuSans.ttf и положите в директорию скрипта

def main():
    root = tk.Tk()
    app = DrawingCheckerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()