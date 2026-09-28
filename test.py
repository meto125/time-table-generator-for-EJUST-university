import pandas as pd
import sys
import os
import random
import time
import math

# ==========================================
# 1. LOAD DATA
# ==========================================
def load_data(base_path):
    print("--- Loading Data ---")
    try:
        rooms = pd.read_csv(os.path.join(base_path, "Rooms.csv"))
        instr = pd.read_csv(os.path.join(base_path, "Instructor.csv"))
        sects = pd.read_csv(os.path.join(base_path, "Sections.csv"))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Normalize Columns
    rooms.columns = [c.lower() for c in rooms.columns]
    cap_col = next((c for c in rooms.columns if 'cap' in c or 'size' in c or 'seat' in c), 'capacity')
    rooms = rooms.rename(columns={'roomid': 'RoomID', 'roomtype': 'RoomType', cap_col: 'Capacity'})
    
    sects.columns = [c.lower() for c in sects.columns]
    size_col = next((c for c in sects.columns if 'size' in c or 'count' in c or 'stud' in c), 'sectionsize')
    sects = sects.rename(columns={'sectionid': 'SectionID', size_col: 'SectionSize'})
    
    return rooms, instr, sects

# ==========================================
# 2. ITERATIVE REPAIR SOLVER (HILL CLIMBING)
# ==========================================
def run_scheduler(base_path):
    rooms_df, instr_df, sects_df = load_data(base_path)
    
    # Prepare Data
    all_rooms = rooms_df['RoomID'].astype(str).tolist()
    room_caps = dict(zip(rooms_df['RoomID'].astype(str), rooms_df['Capacity']))
    
    # Map Room Types
    lab_rooms = rooms_df[rooms_df['RoomType'].str.contains('Lab', case=False, na=False)]['RoomID'].astype(str).tolist()
    lec_rooms = rooms_df[~rooms_df['RoomType'].str.contains('Lab', case=False, na=False)]['RoomID'].astype(str).tolist()

    # Map Instructors
    course_instr_map = {}
    all_instr_ids = instr_df['InstructorID'].astype(str).tolist()
    for _, row in instr_df.iterrows():
        courses = str(row.get('Courses', '')).split(',')
        iid = str(row['InstructorID'])
        for c in courses:
            c = c.strip()
            if c:
                if c not in course_instr_map: course_instr_map[c] = []
                course_instr_map[c].append(iid)

    # Build Solution Objects
    schedule = []
    for _, row in sects_df.iterrows():
        courses = str(row.get('courses', row.get('courseid', ''))).split(',')
        for c in courses:
            c = c.strip()
            if not c: continue
            
            # Determine valid domains
            is_lab = 'LAB' in c.upper()
            valid_rooms = lab_rooms if is_lab else lec_rooms
            valid_rooms = [r for r in valid_rooms if room_caps.get(r, 0) >= row['SectionSize']]
            
            valid_instr = course_instr_map.get(c, all_instr_ids)
            
            if not valid_rooms:
                print(f"CRITICAL: No rooms fit {c} (Size: {row['SectionSize']})")
                continue

            schedule.append({
                "id": str(row['SectionID']),
                "course": c,
                "valid_rooms": valid_rooms,
                "valid_instr": valid_instr,
                # Random Initial Assignment
                "ts": random.randint(1, 20),
                "room": random.choice(valid_rooms),
                "instr": random.choice(valid_instr) if valid_instr else "TBD"
            })

    print(f"Initialized {len(schedule)} assignments. Optimizing (Min-Conflicts)...")

    # --- COST FUNCTION ---
    def calculate_conflicts(sched):
        conflicts = 0
        used_room_ts = {}
        used_instr_ts = {}
        used_sect_ts = {}

        for i, item in enumerate(sched):
            ts = item['ts']
            r = item['room']
            ins = item['instr']
            sid = item['id']

            # Room Conflict
            if (r, ts) in used_room_ts: conflicts += 1
            else: used_room_ts[(r, ts)] = i

            # Instructor Conflict
            if (ins, ts) in used_instr_ts: conflicts += 1
            else: used_instr_ts[(ins, ts)] = i
            
            # Section Conflict (Same section twice at same time? Rare but possible)
            if (sid, ts) in used_sect_ts: conflicts += 1
            else: used_sect_ts[(sid, ts)] = i
            
        return conflicts

    # --- OPTIMIZATION LOOP ---
    current_conflicts = calculate_conflicts(schedule)
    max_steps = 100000
    
    for step in range(max_steps):
        if current_conflicts == 0:
            print(f"\nSOLVED at step {step}!")
            break

        # Pick a random class to change
        idx = random.randint(0, len(schedule) - 1)
        item = schedule[idx]
        
        # Save old state
        old_ts, old_room, old_instr = item['ts'], item['room'], item['instr']
        
        # Randomly change ONE property
        change_type = random.choice(['ts', 'room', 'instr'])
        
        if change_type == 'ts':
            item['ts'] = random.randint(1, 20)
        elif change_type == 'room':
            item['room'] = random.choice(item['valid_rooms'])
        elif change_type == 'instr' and item['valid_instr']:
            item['instr'] = random.choice(item['valid_instr'])

        # Calculate new cost
        new_conflicts = calculate_conflicts(schedule)
        
        # Acceptance Criteria (Hill Climbing: Only accept if better or equal)
        # We accept equal to allow moving across plateaus
        if new_conflicts <= current_conflicts:
            current_conflicts = new_conflicts
        else:
            # Revert
            item['ts'] = old_ts
            item['room'] = old_room
            item['instr'] = old_instr
            
        if step % 5000 == 0:
            print(f"Step {step}: {current_conflicts} conflicts remaining...")

    # --- SAVE ---
    final_df = pd.DataFrame(schedule)
    # Clean up columns for export
    output = final_df[['id', 'course', 'ts', 'room', 'instr']]
    output.columns = ['SectionID', 'CourseID', 'TimeSlotID', 'RoomID', 'InstructorID']
    output.to_csv(os.path.join(base_path, "Scheduled_Sessions.csv"), index=False)
    
    if current_conflicts == 0:
        print("\nSuccess! Schedule saved.")
    else:
        print(f"\nFinished with {current_conflicts} unresolved conflicts. Schedule saved (Best Effort).")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    run_scheduler(path)