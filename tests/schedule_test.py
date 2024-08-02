from ..helpers.schedule import *


def test_course():
    """
    Unit test for Course class
    """
    failure = False
    course_name = "MATEMATICA APLICADA"
    course_days = ["Lunes", "Miercoles", "Viernes"]
    hour_range = "19:01:00 - 19:41:00"
    days = [("Martes", "19:01:00 - 19:41:00"), ("Jueves", "19:01:00 - 19:41:00")]
    test_course_info = [
        ("Lunes", ("19:01:00", "19:41:00")),
        ("Miercoles", ("19:01:00", "19:41:00")),
        ("Viernes", ("19:01:00", "19:41:00")),
        ("Martes", ("19:01:00", "19:41:00")),
        ("Jueves", ("19:01:00", "19:41:00")),
    ]

    # Create course instance
    test_course = Course(course_name)

    # Test get course name method
    if test_course.get_name() != course_name:
        failure = True

    # Test add day method
    for day in course_days:
        test_course.add_day(day, hour_range)

    # Test add days method
    test_course.add_days(days)

    # Test get course info method
    if test_course.get_info() != test_course_info:
        failure = True

    # Test get hours methods
    if test_course.get_hours("Lunes") != ("19:01:00", "19:41:00"):
        failure = True

    if failure:
        print("FAILURE: Course class")
    else:
        print("SUCCESS: Course class")


def test_schedule():
    """
    Unit test for Schedule Class
    """
    failure = False
    test_course = Course("MATEMATICA APLICADA")
    test_course.add_days(
        [
            ("Lunes", "19:01:00 - 19:41:00"),
            ("Miercoles", "19:01:00 - 19:41:00"),
            ("Viernes", "19:01:00 - 19:41:00"),
        ]
    )

    test_course2 = Course("INGENIERIA DE REQUISITOS")
    test_course2.add_days(
        [
            ("Lunes", "19:01:00 - 19:41:00"),
            ("Miercoles", "19:01:00 - 19:41:00"),
            ("Viernes", "19:01:00 - 19:41:00"),
        ]
    )

    test_schedule = Schedule()

    # Test adding a new course course method
    if not test_schedule.add_course(test_course):
        failure = True
    # Test adding a course that not fit in schedule
    if test_schedule.add_course(test_course2):
        failure = True

    # Test get courses method
    if test_schedule.get_courses() != [test_course]:
        failure = True

    # Test print Schedule
    print(test_schedule)

    if failure:
        print("FAILURE: Schedule class")
    else:
        print("SUCCESS: Schedule class")


print("-" * 50)
print("Testing Course class...")
test_course()
print("-" * 50)
print("Testing Schedule class...")
test_schedule()
