"""Модуль отображения таблицы расписания"""
from PyQt5 import uic
from PyQt5.QtWidgets import QWidget, QMessageBox, QHeaderView, QTableWidgetItem, \
    QFileDialog
from login import Login_window
from functions import center, user_size
from PyQt5 import QtGui
import sqlite3
import sys
import csv


class Table(QWidget):
    """Основной класс таблицы расписания"""

    def __init__(self, Uname=None, parent=None, clear=False):
        """Созадет QWidget таблицу расписания
        :param Uname: пользователь
        :param parent: родительское окно
        :param clear: True - пустая таблица

        """

        super(Table, self).__init__()
        self.clear = clear
        self.par = parent  # так получаем сыылку на родительское окно для использования на кнопке назад
        uic.loadUi("table.ui", self)
        user_size(self)
        center(self)
        self.userName = Uname
        con = sqlite3.connect('db1.db')
        cur = con.cursor()
        self.userRight = self.par.userRight
        self.lbl_user.setText(Uname)
        # Описание кнопок
        self.bback.clicked.connect(self.back)  # Кнопка НАЗАД
        self.bsave.clicked.connect(self.save)  # Кнопка СОХРАНИТЬ
        self.bimport.clicked.connect(self.import_table)  # Кнопка ЗАГРУЗИТЬ РАСПИСАНИЕ
        self.bexport.clicked.connect(self.export_table)  # Кнопка СОХРАНИТЬ РАСПИСАНИЕ
        self.bcancel.clicked.connect(self.cancel)  # Кнопка ОТМЕНА
        # заполнение таблицы из бд
        if not clear:
            self.fill_table()
        # растягиваем таблицу на все пространство
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalSlider.valueChanged[int].connect(self.changeValue)

    def changeValue(self, value):
        """Изменение размера шрифта таблицы
        :param value: размер шрифта

        """
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                if self.table.item(row, column):
                    self.table.item(row, column).setFont(QtGui.QFont("Times", 5 + value))

    def save(self):
        """Кнопка СОХРАНИТЬ"""
        if self.clear:
            clear_error = QMessageBox.question(self, "ВНИМАНИЕ!!!", "Действие уничтожит существующее расписание!!!",
                                               QMessageBox.Yes | QMessageBox.No)
            if clear_error == QMessageBox.Yes:
                self.save_changes()
            else:
                self.fill_table()
        else:
            self.save_changes()

    def save_changes(self):
        """Сохраняет таблицу, если при сохранении выявляются дубли учеников/препоадвателей, появлется диалоговое окно"""
        con = sqlite3.connect('db1.db')
        cur = con.cursor()
        sql = '''SELECT timetable.lesson,user.login,student.surname FROM timetable,user,student WHERE 
                                                timetable.teacher_id=user.id AND student.id=timetable.student_id'''
        all_lessons = cur.execute(sql).fetchall()
        # Создаем из результата запроса к ДБ словарь, где ключ урок, а содержимое - список кортежей учитель-ученик
        dic_lesson = {}
        for item in all_lessons:
            lesson, teacher, student = item
            if lesson in dic_lesson:
                dic_lesson[lesson].append((teacher, student))
            else:
                dic_lesson[lesson] = [(teacher, student)]
        if self.userRight == 'teacher':
            teacher = self.userName
            record_ok=False
            uid = "SELECT id from user WHERE login='{}'".format(str(teacher))
            tid = cur.execute(uid).fetchall()[0][0]
            # Сравниваем текущее состояние таблицы со словарем
            for row in range(self.table.rowCount()):
                for column in range(self.table.columnCount()):
                    lesson=str(row)+' '+str(column)
                    if self.table.item(row, column): # Перебираем ячейке таблицы, где есть запись
                        if lesson not in dic_lesson:  # Если в общем расписании урок свободен, можем записать
                            record = True
                        else: # Если в общем расписании на этом уроке есть занятия
                            sql = "SELECT timetable.lesson, user.login FROM timetable,student,user WHERE user.id=timetable.teacher_id AND student.id=timetable.student_id AND student.surname='"+self.table.item(row, column).text()+"'"
                            student_lessons = dict(cur.execute(sql).fetchall())
                            if lesson in student_lessons:  # Проверяем уроки уже существующие в общем расписании
                                if student_lessons[lesson]!=self.userName: # у ученика не может быть несколько уроков одновременно
                                    save_error = QMessageBox.information(self, 'Ошибка сохранения',
                                                                          "У {} уже занят урок {}".format(self.table.item(row, column).text(),lesson))
                                record = False
                            else: # Проверяем, что не произошло изменений в существующих записях
                                record = True
                                for lesson_in_tt in filter(lambda x: x[0]==self.userName,dic_lesson[lesson]):
                                    if lesson_in_tt[1]!=self.table.item(row, column).text():
                                        add_student_error = QMessageBox.information(self, 'Ошибка сохранения',
                                                                            "Перенос занятий {} должен быть согласован администратором".format(
                                                                                lesson_in_tt[1]))
                                        self.fill_table()
                                        record = False
                                        break

                        if record:
                            record_ok=True
                            student = self.table.item(row, column).text()
                            sql = "SELECT id from student WHERE surname='{}'".format(str(student))
                            sid=cur.execute(sql).fetchall()
                            if sid:
                                sid = sid[0][0]
                            else:
                                sql = 'SELECT MAX(id) FROM student'
                                sid = cur.execute(sql).fetchall()[0][0]+1
                                sql = '''INSERT INTO student(id,surname) VALUES (?, ?)'''  # по id записываем уроки в расписание
                                cur.execute(sql, (sid, student))
                            sql = '''INSERT INTO timetable(teacher_id, lesson,student_id) VALUES (?, ?,?)'''  # по id записываем уроки в расписание
                            cur.execute(sql, (tid, lesson,sid))
            con.commit()
            if record_ok:
                clear_error = QMessageBox.information(self, "ОК", "Расписание обновлено.")
        elif self.userRight=='admin':
            sql = "SELECT name,id from user"
            dic_tid=dict(cur.execute(sql).fetchall())
            sql = "SELECT surname,id from student"
            dic_sid = dict(cur.execute(sql).fetchall())
            sid=1
            cur.execute('DELETE FROM timetable')
            for row in range(self.table.rowCount()):
                for column in range(self.table.columnCount()):
                    lesson = str(row) + ' ' + str(column)
                    if self.table.item(row, column) and self.table.item(row, column).text():  # Перебираем ячейке таблицы, где есть запись
                        for item in self.table.item(row, column).text().strip().split('\n'):
                            teacher, student = item.split()
                            if student not in dic_sid:
                                sql = 'SELECT MAX(id) FROM student'
                                sid = cur.execute(sql).fetchall()[0][0] + 1
                                sql = '''INSERT INTO student(id,surname) VALUES (?, ?)'''
                                cur.execute(sql, (sid, student))
                            else:
                                sid = dic_sid[student]
                            if teacher not in dic_tid:
                                sql = 'SELECT MAX(id) FROM user'
                                tid = cur.execute(sql).fetchall()[0][0] + 1
                                sql = '''INSERT INTO user(id,name) VALUES (?, ?)'''
                                cur.execute(sql, (tid, teacher))
                            else:
                                tid = dic_tid[teacher]

                            sql = '''INSERT INTO timetable(teacher_id, lesson,student_id) VALUES (?, ?,?)'''  # по id записываем уроки в расписание
                            cur.execute(sql, (tid, lesson, sid))
            con.commit()
            clear_error = QMessageBox.information(self, "ОК", "Расписание обновлено.")
        else:
            login_error = QMessageBox.information(self, 'Ошибка авторизации',
                                                  "Для внесения изменений авторизуйтесь, пожалуйста.")
            if login_error == QMessageBox.Ok:
                self.menu_login()

    def import_table(self):
        """Сохранение текущего вида расписания в файл timetable.csv"""
        fname = QFileDialog.getOpenFileName(self, 'Open file')
        print(fname[-3:])
        if fname[-3:] != 'csv':
            clear_error = QMessageBox.information(self, "Ошибка", "Расписание должно быть в формате .csv")
        else:
            with open(fname[0], encoding="utf8") as csvfile:
                reader = csv.reader(csvfile, delimiter=';', quotechar='"')
                self.clear_table()
                for i, row in enumerate(reader):
                    for j, cell in enumerate(row):
                        if cell:
                            self.table.setItem(i, j, QTableWidgetItem(cell))

    def export_table(self):
        """Загрузка расписания из файла csv, для сохранения расписания в бд требуется нажать кнопку СОХРАНИТЬ"""
        with open('timetable.csv', 'w', newline='', encoding="utf8") as csvfile:
            writer = csv.writer(
                csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for i in range(self.table.rowCount()):
                row = []
                for j in range(self.table.columnCount()):
                    cell = self.table.item(i, j)
                    if cell:
                        row.append(self.table.item(i, j).text())
                    else:
                        row.append('')
                writer.writerow(row)

    def cancel(self):
        """Кнопка ОТМЕНА"""
        self.clear_table()
        self.fill_table()

    def clear_table(self):
        """Кнопка ОТМЕНА"""
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                if self.table.item(row, column):
                    self.table.setItem(row, column, None)

    def fill_table(self):
        """Заполнение таблицы из бд"""
        con = sqlite3.connect('db1.db')
        cur = con.cursor()
        if self.userRight == 'admin' or self.userRight == None:
            sql = '''SELECT DISTINCT timetable.lesson FROM timetable'''  # Выбираем все существующие уроки в расписании
        else:
            sql = '''SELECT DISTINCT timetable.lesson FROM timetable,user WHERE 
                    timetable.teacher_id=user.id AND user.login="{}"'''.format(
                self.userName)  # Выбираем все существующие уроки данного учителя в расписании
        result = cur.execute(sql).fetchall()
        for item in result:
            row,column=map(int,item[0].split())
            if self.userRight == 'admin' or self.userRight == None:
                if self.userRight is None:
                    self.bcancel.hide()
                    self.bsave.hide()
                    self.bimport.hide()
                sql= '''SELECT user.name, student.surname FROM timetable,user,student WHERE
                        timetable.teacher_id=user.id AND student.id=timetable.student_id AND timetable.lesson="{}"'''.format(item[0])
                self.resize(self.width() * 1.01, self.height() * 1.02)
                center(self)
                day = '\n'.join([' '.join(list(item)) for item in cur.execute(sql).fetchall()])
            else:
                self.bimport.hide()
                sql = '''SELECT student.surname FROM timetable,user,student WHERE
                                        timetable.teacher_id=user.id AND student.id=timetable.student_id AND timetable.lesson="{}" AND user.login="{}"'''.format(item[0],self.userName)
                day = cur.execute(sql).fetchone()[0]
            self.table.setItem(row,column, QTableWidgetItem(day))
        con.close()

    def back(self):
        """Кнопка НАЗАД"""
        self.par.show()  # показываем родительское окно
        self.close()

    def menu_login(self):
        """Окно авторизации"""
        self.wlogin = Login_window(self)
        self.wlogin.show()



