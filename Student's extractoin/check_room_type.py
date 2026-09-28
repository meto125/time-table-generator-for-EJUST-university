import csv

# Allowed mappings
allowed_room_types = {
    "Lecture": ["Classroom", "Hall", "Theater"],
    "Lab": ["Lab"]
}

# Load room types
room_types = {}

with open('Rooms.csv', newline='', encoding='utf-8-sig') as file:
    reader = csv.DictReader(file)
    for row in reader:
        room_id = row['RoomID']
        room_type = row['RoomType']
        room_types[room_id] = room_type


# Check timetable for mismatches
mismatches_found = False

with open('timetable_sections_roomtyped.csv', newline='', encoding='utf-8-sig') as file:
    reader = csv.DictReader(file)
    for row in reader:
        room = row['RoomID']
        component = row['Component']   # Lecture or Lab
        
        # If room not found in room list, warn and skip
        if room not in room_types:
            print(f"⚠️ Room {room} not found in Rooms.csv")
            continue
        
        room_type = room_types[room]
        
        # Validate
        if room_type not in allowed_room_types.get(component, []):
            mismatches_found = True
            print(f"\n❌ Room Type Mismatch:")
            print(f"   Section: {row['SectionID']}")
            print(f"   Course: {row['CourseID']} ({component})")
            print(f"   Assigned Room: {room} ({room_type}) — Not allowed!")


if not mismatches_found:
    print("✅ All room assignments match course type correctly.")
