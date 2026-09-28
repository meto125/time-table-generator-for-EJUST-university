from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")  
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_pdf import PdfPages
import re
import time
from flask import flash


# ==================================================
# Main Scheduler Function
# Runs the scheduling algorithm and outputs a CSV
# ==================================================
def run_scheduler(base: Path):

    # ---------- Track execution time ----------
    start_time = time.time()

    # ---------- Counters for different constraint violations ----------
    violation_counts = {
        "room_conflict": 0,
        "instructor_conflict": 0,
        "section_conflict": 0,
        "capacity_violation": 0,
        "no_room_type_available": 0,
        "no_instructor_available": 0
    }

    # ---------- Base data directory ----------
    data_dir = base / "Student's extractoin"

    # ==================================================
    # Load Input CSV Data
    # ==================================================
    ts = pd.read_csv(data_dir / "TimeSlots.csv")
    rooms = pd.read_csv(data_dir / "Rooms.csv")
    courses = pd.read_csv(data_dir / "Courses.csv")
    instructors = pd.read_csv(data_dir / "Instructor.csv")
    ic_map = pd.read_csv(data_dir / "InstructorCourses.csv")
    sections = pd.read_csv(data_dir / "Sections.csv")


    # ==================================================
    # Helper: Parse list-like strings (e.g. "[A,B,C]")
    # ==================================================
    def parse_list_like(val):
        if pd.isna(val):
            return []
        s = str(val).strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        parts = re.split(r"[;,]", s)
        return [p.strip().strip("'").strip('"') for p in parts if p.strip()]


    # ==================================================
    # Helper: Normalize component names (lecture / lab)
    # ==================================================
    def canon_component(x):
        t = str(x).strip().lower()
        if "lab" in t or "practic" in t:
            return "lab"
        return "lecture"


    # ==================================================
    # Helper: Normalize room types
    # ==================================================
    def canon_room_type(x):
        t = str(x).strip().lower()
        if "lab" in t or "practic" in t:
            return "lab"
        if "class" in t or "lectur" in t or "hall" in t or "theat" in t:
            return "lecture"
        return "lecture"


    # ==================================================
    # Normalize TimeSlots table
    # ==================================================
    tsn = ts.rename(columns={
        "TimeSlotID": "TimeSlotID",
        "Day": "Day",
        "StartTimeTxt": "StartTime",
        "EndTimeTxt": "EndTime",
        "StartMin": "StartMin",
        "EndMin": "EndMin"
    }).copy()

    for c in ["TimeSlotID", "Day", "StartTime", "EndTime"]:
        tsn[c] = tsn[c].astype(str)

    tsn["TimeSlotID"] = tsn["TimeSlotID"].astype(str)


    # ==================================================
    # Normalize Rooms table
    # ==================================================
    rnm = rooms.rename(columns={
        "RoomID": "RoomID",
        "RoomType": "RoomType",
        "Capacity": "Capacity",
        "Building": "Building",
        "RoomName": "RoomName"
    }).copy()

    rnm["RoomID"] = rnm["RoomID"].astype(str)
    rnm["RoomType"] = rnm["RoomType"].astype(str)
    rnm["CanonType"] = rnm["RoomType"].apply(canon_room_type)

    if "Capacity" in rnm:
        rnm["Capacity"] = pd.to_numeric(rnm["Capacity"], errors="coerce")


    # ==================================================
    # Normalize Courses table
    # ==================================================
    cnm = courses.rename(columns={
        "CourseID": "CourseID",
        "CourseName": "CourseName",
        "Type": "CourseType",
        "Credits": "Credits",
        "HasLecture": "HasLecture",
        "HasLab": "HasLab",
        "Year": "Year",
        "Specialization": "Specialization"
    }).copy()

    cnm["CourseID"] = cnm["CourseID"].astype(str)
    cnm["CourseName"] = cnm["CourseName"].astype(str)
    cnm["CourseType"] = cnm["CourseType"].astype(str)
    cnm["HasLecture"] = cnm["HasLecture"].astype(str).str.lower().isin(["1","true","yes","y","t"])
    cnm["HasLab"] = cnm["HasLab"].astype(str).str.lower().isin(["1","true","yes","y","t"])

    if "Credits" in cnm:
        cnm["Credits"] = pd.to_numeric(cnm["Credits"], errors="coerce")


    # ==================================================
    # Normalize Instructors table
    # ==================================================
    inm = instructors.rename(columns={
        "InstructorID": "InstructorID",
        "Name": "InstructorName",
        "PreferredSlots": "PreferredSlots",
        "QualifiedCourses": "QualifiedCourses"
    }).copy()

    inm["InstructorID"] = inm["InstructorID"].astype(str)
    inm["InstructorName"] = inm["InstructorName"].astype(str)
    inm["PreferredSlotIDs"] = inm["PreferredSlots"].apply(parse_list_like) if "PreferredSlots" in inm else [[]] * len(inm)
    inm["QualifiedCourseIDs"] = inm["QualifiedCourses"].apply(parse_list_like) if "QualifiedCourses" in inm else [[]] * len(inm)


    # ==================================================
    # Normalize Instructor-Course mapping
    # ==================================================
    icm = ic_map.rename(columns={
        "InstructorID": "InstructorID",
        "CourseID": "CourseID"
    }).copy()

    icm["InstructorID"] = icm["InstructorID"].astype(str)
    icm["CourseID"] = icm["CourseID"].astype(str)


    # ==================================================
    # Normalize Sections and expand sessions
    # ==================================================
    sec = sections.copy()
    sec_cols = {c.lower(): c for c in sec.columns}

    section_id_col = sec_cols.get("sectionid")
    course_list_col = sec_cols.get("courses")

    secn = pd.DataFrame()
    secn["SectionID"] = sec[section_id_col].astype(str)
    secn["CourseIDs"] = sec[course_list_col].apply(parse_list_like)


    # ==================================================
    # Expand each section-course into lecture/lab sessions
    # ==================================================
    course_info = cnm.set_index("CourseID")[["CourseName", "HasLecture", "HasLab"]]

    session_rows = []
    for _, row in secn.iterrows():
        sect = row["SectionID"]

        for c_id in row["CourseIDs"]:
            c_id = str(c_id)
            cname = None
            has_lec = False
            has_lab = False

            if c_id in course_info.index:
                meta = course_info.loc[c_id]
                cname = meta["CourseName"]
                has_lec = bool(meta["HasLecture"])
                has_lab = bool(meta["HasLab"])

            components = []
            if has_lec:
                components.append("Lecture")
            if has_lab:
                components.append("Lab")
            if not components:
                components = ["Lecture"]

            for comp in components:
                session_rows.append({
                    "SectionID": sect,
                    "CourseID": c_id,
                    "CourseName": cname,
                    "Component": comp,
                    "CanonComponent": canon_component(comp)
                })

    sessions_df = pd.DataFrame(session_rows)


    # ==================================================
    # Build eligible instructors map
    # ==================================================
    eligible_map = {}

    for c_id, grp in icm.groupby("CourseID"):
        eligible_map.setdefault(c_id, set()).update(grp["InstructorID"].tolist())

    for _, ins in inm.iterrows():
        for q in ins["QualifiedCourseIDs"]:
            eligible_map.setdefault(str(q), set()).add(ins["InstructorID"])

    def eligible_instructors(course_id):
        return sorted(list(eligible_map.get(str(course_id), [])))


    # ==================================================
    # Prepare rooms and timeslots
    # ==================================================
    all_ts = tsn["TimeSlotID"].astype(str).tolist()
    rooms_by_canon = rnm.groupby("CanonType")["RoomID"].apply(list).to_dict()

    def rooms_for_component(component):
        return rooms_by_canon.get(canon_component(component), [])


    # ==================================================
    # Capacity constraint check
    # ==================================================
    def capacity_ok(room_id, section_size):
        if section_size is None or pd.isna(section_size):
            return True
        row = rnm.loc[rnm["RoomID"] == room_id, "Capacity"]
        if row.empty or pd.isna(row.iloc[0]):
            return True
        return float(row.iloc[0]) >= float(section_size)


    # ==================================================
    # Sort sessions (most constrained first)
    # ==================================================
    def var_key(row):
        rc = len(rooms_for_component(row["Component"]))
        ec = max(1, len(eligible_instructors(row["CourseID"])))
        return (rc, ec)

    if not sessions_df.empty:
        sessions_df["SortKey"] = sessions_df.apply(var_key, axis=1)
        sessions_df = sessions_df.sort_values("SortKey").drop(columns=["SortKey"]).reset_index(drop=True)


    # ==================================================
    # Backtracking Scheduler
    # ==================================================
    assignments = []
    used_instr_ts = set()
    used_room_ts = set()
    used_sect_ts = set()

    def backtrack(i):
        if i >= len(sessions_df):
            return True

        row = sessions_df.iloc[i]
        comp_rooms = rooms_for_component(row["Component"])

        if not comp_rooms:
            violation_counts["no_room_type_available"] += 1
            return False

        elig = eligible_instructors(row["CourseID"]) or inm["InstructorID"].tolist()
        if not elig:
            violation_counts["no_instructor_available"] += 1
            return False

        for ts_id in all_ts:
            if (row["SectionID"], ts_id) in used_sect_ts:
                violation_counts["section_conflict"] += 1
                continue

            for room_id in comp_rooms:
                if (room_id, ts_id) in used_room_ts:
                    violation_counts["room_conflict"] += 1
                    continue

                for instr_id in elig:
                    if (instr_id, ts_id) in used_instr_ts:
                        violation_counts["instructor_conflict"] += 1
                        continue

                    # Assign resources
                    used_sect_ts.add((row["SectionID"], ts_id))
                    used_room_ts.add((room_id, ts_id))
                    used_instr_ts.add((instr_id, ts_id))

                    assignments.append({
                        "TimeSlotID": ts_id,
                        "RoomID": room_id,
                        "InstructorID": instr_id,
                        "SectionID": row["SectionID"],
                        "CourseID": row["CourseID"],
                        "CourseName": row["CourseName"],
                        "Component": row["Component"]
                    })

                    if backtrack(i + 1):
                        return True

                    # Undo assignment
                    assignments.pop()
                    used_sect_ts.remove((row["SectionID"], ts_id))
                    used_room_ts.remove((room_id, ts_id))
                    used_instr_ts.remove((instr_id, ts_id))

        return False


    # ==================================================
    # Run scheduler and build output
    # ==================================================
    feasible = backtrack(0)
    sched = pd.DataFrame(assignments)

    if not sched.empty:
        sched = (
            sched.merge(tsn, on="TimeSlotID", how="left")
                 .merge(inm[["InstructorID", "InstructorName"]], on="InstructorID", how="left")
        )

    out_csv = base / "timetable_sections_roomtyped.csv"
    sched.to_csv(out_csv, index=False)

    # ---------- Final execution stats ----------
    execution_time = round(time.time() - start_time, 2)

    result = {
        "feasible": bool(len(assignments) == len(sessions_df) and len(assignments) > 0),
        "total_sessions": int(len(sessions_df)),
        "scheduled": int(len(assignments)),
        "execution_time_sec": execution_time,
        "violation_counts": violation_counts,
        "outputs": {
            "sections_csv": out_csv.name,
        },
        "base_path": str(base.resolve()),
    }

    return result
