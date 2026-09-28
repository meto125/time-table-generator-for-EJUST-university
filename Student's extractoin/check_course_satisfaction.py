import csv

# Step 1: Load course requirements (Lecture/Lab)
course_requirements = {}

with open('Courses.csv', newline='', encoding='utf-8-sig') as file:
    reader = csv.DictReader(file)
    for row in reader:
        course = row['CourseID']
        has_lec = row['HasLecture'] == '1'
        has_lab = row['HasLab'] == '1'
        
        required_components = []
        if has_lec:
            required_components.append((course, "Lecture"))
        if has_lab:
            required_components.append((course, "Lab"))
        
        course_requirements[course] = required_components


# Step 2: Load required courses per section
section_required = {}

with open('Sections.csv', newline='', encoding='utf-8-sig') as file:
    reader = csv.DictReader(file)
    for row in reader:
        section = row['SectionID']   # BOM is removed now
        courses = [c.strip() for c in row['Courses'].split(',')]
        
        required_components = []
        for course in courses:
            if course in course_requirements:
                required_components.extend(course_requirements[course])

        
        section_required[section] = required_components


# Step 3: Load scheduled components from timetable
section_scheduled = {}

with open('timetable_sections_roomtyped.csv', newline='', encoding='utf-8-sig') as file:
    reader = csv.DictReader(file)
    for row in reader:
        section = row['SectionID']
        course = row['CourseID']
        comp = row['Component']  # Lecture / Lab
        
        section_scheduled.setdefault(section, []).append((course, comp))


missing_requirements = False

for section, required in section_required.items():
    scheduled = section_scheduled.get(section, [])
    
    missing = [req for req in required if req not in scheduled]
    
    if missing:
        missing_requirements = True
        print(f"\n❌ Section {section} is missing:")
        for course, comp in missing:
            print(f"   - {course} {comp}")

if not missing_requirements:
    print("✅ All sections have their required Lecture/Lab components scheduled.")