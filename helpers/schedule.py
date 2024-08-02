from texttable import Texttable

FILE_NAME = "2do_semestre.csv"


class Schedule:
    DAYS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]

    HOURS_WEEK = [
        "19:01:00",
        "19:41:00",
        "20:20:00",
        "20:31:00",
        "21:10:00",
        "21:11:00",
        "21:50:00",
        "22:30:00",
    ]
    HOURS_WEEKEND = [
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

    BLOCKS_WEEK = [
        ("19:01:00", "19:40:00"),
        ("19:41:00", "20:20:00"),
        ("20:31:00", "21:10:00"),
        ("21:11:00", "21:50:00"),
        ("21:11:00", "21:50:00"),
        ("21:51:00", "22:30:00"),
    ]

    BLOCKS_WEEKEND = [
        ("8:31:00", "9:10:00"),
        ("9:11:00", "9:50:00"),
        ("10:01:00", "10:40:00"),
        ("10:41:00", "11:20:00"),
        ("11:31:00", "12:10:00"),
        ("12:11:00", "12:50:00"),
        ("13:01:00", "13:40:00"),
        ("13:41:00", "14:20:00"),
        ("14:31:00", "15:10:00"),
        ("15:11:00", "15:50:00"),
    ]

    def __init__(self):
        self.courses = []
        self.week_schedule = [
            [None for _ in range(5)] for _ in range(len(Schedule.HOURS_WEEK))
        ]
        self.weekend_schedule = [None for _ in range(len(Schedule.HOURS_WEEKEND))]

    def __str__(self):
        table_week = Texttable()
        table_week.add_row(["Horas", *Schedule.DAYS[:-1]])
        for index, hour in enumerate(Schedule.HOURS_WEEK):
            table_week.add_row([hour, *self.get_week_schedule()[index]])

        table_weekend = Texttable()
        table_weekend.add_row(["Horas", *Schedule.DAYS[-1:]])
        for index, hour in enumerate(Schedule.HOURS_WEEKEND):
            table_weekend.add_row([hour, self.get_weekend_schedule()[index]])

        return table_week.draw() + "\n" + table_weekend.draw()

    def get_week_schedule(self):
        return self.week_schedule

    def get_weekend_schedule(self):
        return self.weekend_schedule

    def get_courses(self):
        return self.courses

    def add_course(self, course):
        try:

            for day_info in course.get_info():
                day, hours_info = day_info
                hour_start, hour_end = hours_info

                if day != "Sabado":
                    block = Schedule.HOURS_WEEK
                    schedule = self.week_schedule
                else:
                    block = Schedule.HOURS_WEEKEND
                    schedule = self.weekend_schedule

                slot_start = block.index(hour_start)
                slot_end = block.index(hour_end)
                day_index = Schedule.DAYS.index(day)

                for i in range(slot_start, slot_end + 1):
                    if schedule[i][day_index]:
                        raise ValueError("Error adding course", course.get_name())
                    else:
                        schedule[i][day_index] = course.get_name()

            self.courses.append(course)
            print(f"{course.get_name()} added")
            return True
        except ValueError:
            return False


class Course:
    def __init__(self, course_name):
        self.info = {}
        self.course_name = course_name

    def __str__(self):
        return str(self.info)

    def get_name(self):
        return self.course_name

    def get_info(self):
        info = []
        for day in self.info:
            info.append((day, self.info[day]))
        return info

    def add_day(self, day, hour_range):
        hour_start, hour_end = hour_range.split(" - ")
        self.info.setdefault(day, (hour_start, hour_end))

    def add_days(self, days):
        """
        add multiple days to a course.

        days: list of tuples of strings [('day', 'hour_start - hour_end')]
        """
        for day in days:
            day_of_the_week, hours = day
            hour_start, hour_end = hours.split(" - ")
            self.info.setdefault(day_of_the_week, (hour_start, hour_end))

    def get_hours(self, day):
        return self.info[day]
