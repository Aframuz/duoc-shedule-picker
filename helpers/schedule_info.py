import csv
import random
import pprint

FILE_NAME = "2do_semestre.csv"
courses = {}


def parse_schedule(schedule):
    """
    convert schedule string into a tuple (day, (block start index, block end index))

    schedule: string
    returns: tuple
    """

    days_codes = {
        "Lu": "Monday",
        "Ma": "Tuesday",
        "Mi": "Wednesday",
        "Ju": "Thursday",
        "Vi": "Friday",
        "Sa": "Saturday",
    }

    hour_blocks_week = [
        "19:01:00",
        "19:41:00",
        "20:20:00",
        "20:31:00",
        "21:10:00",
        "21:11:00",
        "21:50:00",
        "22:30:00",
    ]

    hour_blocks_weekend = [
        "8:31:00",
        "9:50:00",
        "10:01:00",
        "11:20:00",
        "11:31:00",
        "12:10:00",
        "12:11:00",
        "12:50:00",
        "13:01:00",
        "13:40:00",
        "14:20:00",
        "14:31:00",
        "15:50:00",
    ]

    schedule_day = schedule[:2]
    schedule_hours = schedule[3:]
    schedule_hour_start, schedule_hours_end = schedule_hours.split(" - ")

    if days_codes[schedule_day] != "Saturday":
        blocks = hour_blocks_week
    else:
        blocks = hour_blocks_weekend

    return (
        days_codes[schedule_day],
        (
            blocks.index(schedule_hour_start),
            blocks.index(schedule_hours_end),
        ),
    )


def parse_course_section(course_code):
    """
    extract section of a course using the section code

    course_code: string
    returns: string (section code)
    """
    return course_code[-4:]


with open(FILE_NAME, "r", encoding="utf-8") as schedule:
    csv_reader = csv.DictReader(schedule)

    for row in csv_reader:
        # extract info
        ramo = row["Ramo"]
        seccion = parse_course_section(row["Codigo"])
        horario = row["Horario"]

        # create course key
        courses.setdefault(ramo, {})

        # if course section doesn't exists, append it
        courses[ramo].setdefault(seccion, [])

        courses[ramo][seccion].append(parse_schedule(horario))
