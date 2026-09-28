import csv

def to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m

def find_collisions(schedule):
    collisions = []
    for i in range(len(schedule)):
        day1, start1, end1 = schedule[i]
        start1_m, end1_m = to_minutes(start1), to_minutes(end1)

        for j in range(i + 1, len(schedule)):
            day2, start2, end2 = schedule[j]
            start2_m, end2_m = to_minutes(start2), to_minutes(end2)

            # Same day + overlapping time
            if day1 == day2 and start1_m < end2_m and end1_m > start2_m:
                collisions.append(((day1, start1, end1), (day2, start2, end2)))

    return collisions


prof_schedules = {}

# READ CSV
with open('timetable_sections_roomtyped.csv', newline='') as file:
    reader = csv.DictReader(file)
    for row in reader:
        prof = row['InstructorID']
        day = row['Day']
        start = row['StartTime']
        end = row['EndTime']
        
        prof_schedules.setdefault(prof, []).append((day, start, end))

# print(prof_schedules)

no_collisions = True

for prof, schedule in prof_schedules.items():
    collisions = find_collisions(schedule)

    if collisions:
        no_collisions = False
        print(f"\n⚠️ Collisions for {prof}:")
        for c1, c2 in collisions:
            print(f"   • {c1[0]}: {c1[1]}-{c1[2]} overlaps with {c2[1]}-{c2[2]}")

if no_collisions:
    print("✅ No professor schedule collisions found.")