'''
 *  Copyright (C) 2015 Touch Vectron
 *
 *  Author: Cornel Punga
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License version 2 as
 *  published by the Free Software Foundation.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
 *  MA 02110-1301, USA.
 *
 *	Filename: CheckParser.py
 *	This module will parse files.txt (this is where the check from POS is written)
 *      and then will output related information to bon.txt (file from where the printer
 *      reads the check)
 *
 *	Last revision: 05/31/2015
 *
'''

from datetime import datetime
from time import sleep
from re import search, sub
from inspect import stack
from subprocess import Popen
from CheckLogger import check_logger


class CheckParser(object):
    def __init__(self, position, filename=None):
        self.check_data = []
        self.check_to_print = []
        self.position = position
        self.filename = filename
        self.cash = None
        self.card = None

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        if value is not None:
            if value >= 0:
                self._position = value
            else:
                raise ValueError("Initial position must be a natural number")

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, value):
        if value is not None:
            self._filename = value
        else:
            self._filename = r"C:\Vectron\VPosPC\files.txt"

    def read_file(self):
        check_logger.debug("{0}: {1}".format(stack()[0][3], "_____START_____"))
        with open(self.filename, "rb") as fh:
            check_logger.debug("{0}: {1}".format(stack()[0][3], "file.txt opened"))
            fh.seek(self.position)
            line = fh.readline()
            check_logger.debug("{0}: {1}".format(stack()[0][3], line))
            delimiter = "**************************************************"
            while line:
                if delimiter in line:
                    line = fh.readline()
                    check_logger.debug("{0}: {1}".format(stack()[0][3], line))
                    while delimiter not in line:
                        self.check_data.append(line)
                        line = fh.readline()
                        check_logger.debug("{0}: {1}".format(stack()[0][3], line))
                line = fh.readline()
                check_logger.debug("{0}: {1}".format(stack()[0][3], line))
                if "Cash" in line:
                    self.cash = line
                if "Plata card" in line:
                    self.card = line
                if "= Cut =" in line and self.check_data != []:
                    check_logger.debug("{0}: {1}".format(stack()[0][3], self.check_data))
                    self.generate_new_check()
                    CheckParser.write_2_file(self.check_to_print)
                    self.check_to_print = []
                    CheckParser.execute_batch_file()
                    self.check_data = []
                    sleep(0.5)
            self.position = fh.tell()
            check_logger.debug("{0}: {1}".format(stack()[0][3], "_____END_____"))

    def payment_method(self):
        if self.cash:
            backup_list = list(filter(lambda x: x != '', self.cash.split(' ')))
            price = CheckParser.get_field_value('\d+\,\d+', self.cash, backup_list, 1, ',', '', 8)
            self.check_to_print.append("RQ0CASH      " + price + "2\n")
            self.cash = None
        if self.card:
            backup_list = list(filter(lambda x: x != '', self.card.split(' ')))
            price = CheckParser.get_field_value('\d+\,\d+', self.card, backup_list, 2, ',', '', 8)
            self.check_to_print.append("RQ1CARD      " + price + "2\n")
            self.card = None

    def generate_new_check(self):
        check_logger.debug("{0}: {1}".format(stack()[0][3], "starting creation of products and payment"))
        for elem in self.check_data:
            check_logger.debug("{0}: {1}".format(stack()[0][3], elem))
            backup_list = list(filter(lambda x: x != '', elem.split(' ')))
            price = CheckParser.get_field_value('\d+\,\d+', elem, backup_list, 5, ',', '', 8)
            decimals = "2"
            quantity = CheckParser.get_field_value('\d+', elem, backup_list, 0, ',', '', 6) + "000"
            tva = CheckParser.get_field_value('\d{1,2}%', elem, backup_list, 6, '%', '')
            tva = CheckParser.tva_by_time(tva)
            subgroup = "1"
            group = "1"
            prod_name = CheckParser.get_field_value('[a-zA-Z]{2,}[\S\s]?[a-zA-Z]*[\S\s]?[a-zA-Z]*',
                                                    elem, backup_list, 3)
            final_check = '*' + prod_name + " " * (24 - len(prod_name)) + price + decimals + quantity + \
                                                        tva + subgroup + group + '\n'
            check_logger.debug("{0}: {1}".format(stack()[0][3], final_check))
            self.check_to_print.append(final_check)
        check_logger.debug("{0}: {1}".format(stack()[0][3], "finished creation of products and payment"))

    @staticmethod
    def get_field_value(regex_pattern, data_bucket, backup_data,
                        backup_index, subst_from=None, subst_to=None, padding_val=None):
        reg_ex = search(regex_pattern, data_bucket)
        if reg_ex:
            field_value = data_bucket[reg_ex.start():reg_ex.end()]
        else:
            field_value = backup_data[backup_index]
        if subst_from and padding_val:
            field_value = (sub(subst_from, subst_to, field_value)).rjust(padding_val, '0')
        elif subst_from:
            field_value = sub(subst_from, subst_to, field_value)
        else:
            return field_value

        return field_value

    @staticmethod
    def tva_by_time(tva):
        time = datetime.now()
        if tva == "24":
            if 7 <= time.hour < 24:
                tva = "1"
            else:
                tva = "2"
        elif tva == "9":
            tva = "3"
        else:
            tva = "4"

        return tva

    @staticmethod
    def write_2_file(to_print):
        header_line = "KARAT\n"
        footer_line = "T0000010000 TOTAL\nEND KARAT\n"
        file_bon = r"C:\Listener\bon.txt"
        check_logger.debug("{0}: {1}".format(stack()[0][3], to_print))
        with open(file_bon, "w") as fp:
            fp.write(header_line)
            for item in to_print:
                fp.write(item)
            fp.write(footer_line)
        print("Tiparire -> Status: OK!")

    @staticmethod
    def execute_batch_file():
        batch_file_path = r"C:\Listener\start.bat"
        check_logger.debug("{0}: {1}".format(stack()[0][3], "execute batch file"))
        print_job = Popen(batch_file_path, shell=False)
        stdout, stderr = print_job.communicate()


def read_init_pos():
    pos_filepath = r"C:\Vectron\pos.txt"
    with open(pos_filepath, "r") as fp:
        init_pos = fp.readline()
        check_logger.debug("{0}: {1}".format(stack()[0][3], init_pos))
        if init_pos == '':
            init_pos = 0
    return int(init_pos)


def write_init_pos(pos):
    if not isinstance(pos, str):
        try:
            pos = str(pos)
        except (ValueError, TypeError):
            pos = "0"

    pos_filepath = r"C:\Vectron\pos.txt"
    check_logger.debug("{0}: {1}".format(stack()[0][3], pos))
    with open(pos_filepath, "w") as fp:
        fp.write(pos)


def get_file_end_pos():
        filename = r"C:\Vectron\VPosPC\files.txt"
        with open(filename, "r") as ff:
            ff.seek(0, 2)
            check_logger.debug("{0}: {1}".format(stack()[0][3], ff.tell()))
            return int(ff.tell())