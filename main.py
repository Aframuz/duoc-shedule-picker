from schedule_info import courses
from pprint import pprint
from tabulate import tabulate
from texttable import Texttable


def is_valid(week):
    """
    check if a schedule fit in a week
    week structure {course_name: (course_section, course_hours)}

    week: dictionary
    """
    WEEK = {
        "Monday": [None for _ in range(8)],
        "Tuesday": [None for _ in range(8)],
        "Wednesday": [None for _ in range(8)],
        "Thursday": [None for _ in range(8)],
        "Friday": [None for _ in range(8)],
        "Saturday": [None for _ in range(13)],
    }

    for schedule in week.values():
        for hours in schedule[1]:
            day = hours[0]
            h_start = hours[1][0]
            h_end = hours[1][1]
            for i in range(h_start, h_end + 1):
                if WEEK[day][i] != None:
                    return False
                WEEK[day][i] = True

    return True


def traverse_schedules(courses, weeks, depth=0, path=[]):
    """
    append to list a valid week depending on possible course schedules.
    possible week structure {course_name: (course_section, course_hours)}

    returns: None
    """
    if depth == len(courses):
        week = {}
        for i, course in enumerate(courses):
            week.update({course: (path[i], courses[course][path[i]])})
        if is_valid(week) and week not in weeks:
            weeks.append(week)
        return

    key = list(courses.keys())[depth]
    tuples_list = courses[key]

    for t in tuples_list:
        new_path = path + [t]
        traverse_schedules(courses, weeks, depth + 1, new_path)


def week_to_codes(week):
    """
    map a valid week dictionary to a list of tuples containing the course_name and its respective
    course section code

    week: dictionary
    returns: list
    """
    week_to_sections = []
    for course_name, course_info in week.items():
        # course_info[0] containds the course section code
        week_to_sections.append((course_name, course_info[0]))
    return week_to_sections


def only_section_codes(week):
    """
    map a valid week dictionary to a list of course section codes

    week: dictionary
    returns: list
    """

    codes = []
    for info in week.values():
        codes.append(info[0])
    return codes


def week_to_table(week):
    week_table = [
        ["19:01:00", "", "", "", "", ""],
        ["19:41:00", "", "", "", "", ""],
        ["20:20:00", "", "", "", "", ""],
        ["20:31:00", "", "", "", "", ""],
        ["21:10:00", "", "", "", "", ""],
        ["21:11:00", "", "", "", "", ""],
        ["21:50:00", "", "", "", "", ""],
        ["22:30:00", "", "", "", "", ""],
    ]

    weekend_table = [
        ["8:31:00", ""],
        ["9:50:00", ""],
        ["10:01:00", ""],
        ["11:20:00", ""],
        ["11:31:00", ""],
        ["12:10:00", ""],
        ["12:11:00", ""],
        ["12:50:00", ""],
        ["13:01:00", ""],
        ["13:40:00", ""],
        ["14:20:00", ""],
        ["14:31:00", ""],
        ["15:50:00", ""],
    ]

    WEEK_DAYS = [
        "HOURS",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    COURSE_NAME_ABR = {
        "MATEMÁTICA APLICADA": "MATE",
        "DESARROLLO ORIENTADO A OBJETOS": "OOP",
        "INGENIERÍA DE REQUISITOS": "REQ",
        "INGLÉS ELEMENTAL I": "INGLES",
        "BASE DE DATOS APLICADA I": "DATABASE",
        "FUNDAMENTOS DE ANTROPOLOGÍA": "ANTRO",
    }

    for course_name, course_info in week.items():
        for hour in course_info[1]:
            if hour[0] == "Saturday":
                for i in range(hour[1][0], hour[1][1] + 1):
                    weekend_table[i][1] = (
                        COURSE_NAME_ABR[course_name] + " " + course_info[0]
                    )
            else:
                for i in range(hour[1][0], hour[1][1] + 1):
                    week_table[i][WEEK_DAYS.index(hour[0])] = (
                        COURSE_NAME_ABR[course_name] + " " + course_info[0]
                    )

    week_table.insert(0, WEEK_DAYS[:-1])
    weekend_table.insert(0, ["HOURS", "Saturday"])
    # week table
    table_w = Texttable()
    table_w.set_deco(Texttable.HEADER)
    table_w.add_rows(week_table)

    # weekend table
    table_wkn = Texttable()
    table_wkn.set_deco(Texttable.HEADER)
    table_wkn.add_rows(weekend_table)

    return f"{table_w.draw()}\n{table_wkn.draw()}"
    print(tabulate(week_table))
    print(tabulate(weekend_table))
    print("=" * 70)


def filter_by_section(weeks, course_name, section):
    """
    filter out a week in a list of weeks where the input specified matches the
    course name an its section code
    """
    tmp_weeks = []
    for week in weeks:
        if week[course_name][0] == section:
            continue
        tmp_weeks.append(week)
    return tmp_weeks


def main(courses):
    possible_weeks = []
    traverse_schedules(courses, possible_weeks)

    # possible_weeks = filter_by_section(
    #     possible_weeks, "FUNDAMENTOS DE ANTROPOLOGÍA", "042V"
    # )
    # possible_weeks = filter_by_section(
    #     possible_weeks, "FUNDAMENTOS DE ANTROPOLOGÍA", "041V"
    # )
    # possible_weeks = filter_by_section(
    #     possible_weeks, "INGENIERÍA DE REQUISITOS", "009V"
    # )
    # possible_weeks = filter_by_section(
    #     possible_weeks, "BASE DE DATOS APLICADA I", "015V"
    # )

    f = open("schedules.txt", "w")
    i = 1
    for week in possible_weeks:
        # HEADER
        f.write("*" * 80)
        f.write("\n")
        f.write(f"SEMANA {i}".center(80))
        f.write("\n")
        f.write("*" * 80)
        f.write("\n")
        # TABLES
        f.write(week_to_table(week))
        f.write("\n\n")
        i += 1
    f.close()


if __name__ == "__main__":
    main(courses)
