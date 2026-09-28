from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from pathlib import Path
from scheduler_runner import run_scheduler
import os
import csv
import pandas as pd
import hashlib

app = Flask(__name__)
app.secret_key = "dev-secret"

# Default project base directory
DEFAULT_BASE = r"C:\Users\ayman\Desktop\bay prject\proj 1"

# Only these files are allowed to be downloaded
ALLOWED_OUTS = {"timetable_sections_roomtyped.csv"}

# Fixed days and time slots for schedule rendering
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"] 
TIME_SLOTS = [
    "9:00-10:30", 
    "10:45-12:15", 
    "12:30-2:00", 
    "2:15-3:45"
]


# --------------------------------------------------
# Route: Display generated schedule grouped by year,
# section, day, and time slot
# --------------------------------------------------
@app.route("/schedule")
def view_schedule():
    base = Path(DEFAULT_BASE)
    output_file = base / "timetable_sections_roomtyped.csv"

    if not output_file.exists():
        return "Schedule CSV not found", 404

    df = pd.read_csv(output_file)

    # --- LOAD YEAR DATA ---
    sections_file = base / "Student's extractoin" / "Sections.csv"
    courses_file = base / "Student's extractoin" / "Courses.csv"

    sections_df = pd.read_csv(sections_file)
    courses_df = pd.read_csv(courses_file)

    # Map CourseID -> Academic Year
    course_year = courses_df.set_index("CourseID")["Year"].to_dict()

    # Map SectionID -> Academic Year (based on first course found)
    section_year = {}
    for _, row in sections_df.iterrows():
        sec = str(row["SectionID"])
        course_list = str(row["Courses"]).split(",")
        for c in course_list:
            c = c.strip()
            if c in course_year:
                section_year[sec] = int(course_year[c])
                break

    # --- BUILD SCHEDULE STRUCTURE ---
    schedule = {}

    for _, r in df.iterrows():
        section = str(r["SectionID"])
        year = section_year.get(section, 99)  # unknown years go last
        day = str(r["Day"])
        slot = f"{r['StartTime']}-{r['EndTime']}"

        schedule.setdefault(year, {})
        schedule[year].setdefault(section, {})
        schedule[year][section].setdefault(day, {})
        schedule[year][section][day][slot] = {
            "course": f"{r['CourseID']} – {r['CourseName']}",
            "instr": r["InstructorName"],
            "room": r["RoomID"],
            "type": r["Component"],
            "color": color_from_course(r["CourseID"])
        }

    # Sort years and sections
    schedule = dict(sorted(schedule.items()))
    for year in schedule:
        schedule[year] = dict(sorted(schedule[year].items()))

    return render_template(
        "schedule.html",
        schedule=schedule,
        days=DAYS,
        slots=TIME_SLOTS
    )


# --------------------------------------------------
# Generate a consistent pastel HSL color
# for a course based on its CourseID
# --------------------------------------------------
def color_from_course(course_id):
    h = hashlib.md5(course_id.encode()).hexdigest()

    hue = int(h[0:2], 16) * 360 // 255
    sat = 60 if int(h[2], 16) % 2 == 0 else 75
    light = 82 if int(h[3], 16) % 2 == 0 else 70

    return f"hsl({hue}, {sat}%, {light}%)"


# --------------------------------------------------
# Read Sections.csv and return all unique SectionIDs
# --------------------------------------------------
def get_all_sections(base_path):
    try:
        data_dir = Path(base_path) / "Student's extractoin"
        sections_file = data_dir / "Sections.csv"
        if sections_file.exists():
            df = pd.read_csv(sections_file)
            return sorted(df['SectionID'].astype(str).unique().tolist())
    except Exception:
        return []


# --------------------------------------------------
# Read Courses.csv and return sorted (CourseID, CourseName)
# --------------------------------------------------
def get_all_courses(base_path):
    try:
        data_dir = Path(base_path) / "Student's extractoin"
        course_file = data_dir / "Courses.csv"
        if course_file.exists():
            df = pd.read_csv(course_file)
            course_list = df[['CourseID', 'CourseName']].dropna().values.tolist()
            course_list.sort(key=lambda x: x[0])
            return course_list
    except Exception:
        return []


# --------------------------------------------------
# Delete a course completely or from specific sections
# Updates Sections.csv and InstructorCourses.csv
# --------------------------------------------------
def delete_course_logic(base_path, course_id, delete_all=True, target_sections=None):
    data_dir = Path(base_path) / "Student's extractoin"
    target_sections = set(target_sections or [])

    # Remove course from Sections.csv
    s_file = data_dir / "Sections.csv"
    if s_file.exists():
        df_sec = pd.read_csv(s_file)

        def clean_courses(row):
            courses = []
            if pd.notna(row["Courses"]):
                courses = [c.strip() for c in str(row["Courses"]).split(",")]

            if delete_all:
                courses = [c for c in courses if c != course_id]
            elif row["SectionID"] in target_sections:
                courses = [c for c in courses if c != course_id]

            return ",".join(courses)

        df_sec["Courses"] = df_sec.apply(clean_courses, axis=1)
        df_sec.to_csv(s_file, index=False)

    # Remove course from InstructorCourses.csv
    ic_file = data_dir / "InstructorCourses.csv"
    if ic_file.exists():
        df_ic = pd.read_csv(ic_file)
        df_ic = df_ic[df_ic["CourseID"] != course_id]
        df_ic.to_csv(ic_file, index=False)

    flash(f"Course '{course_id}' deleted successfully.", "success")


# --------------------------------------------------
# Add a new course to Courses.csv
# and assign it to selected sections
# --------------------------------------------------
def save_new_course(base_path, course_data, target_sections):
    data_dir = Path(base_path) / "Student's extractoin"
    course_id = course_data.get("CourseID")
    course_file = data_dir / "Courses.csv"

    new_row = [
        course_id, course_data.get("CourseName", ""), course_data.get("Credits", 3),
        course_data.get("Type", "Lecture and Lab"), course_data.get("Year", 4),
        course_data.get("Specialization", "Common"), course_data.get("HasLecture", 1),
        course_data.get("HasLab", 1), course_data.get("IsGradProject", 0)
    ]

    try:
        file_exists = course_file.exists()
        with open(course_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists or os.path.getsize(course_file) == 0:
                writer.writerow(["CourseID","CourseName","Credits","Type","Year",
                                 "Specialization","HasLecture","HasLab","IsGradProject"])
            writer.writerow(new_row)
        flash(f"Course '{course_id}' added.", "success")
    except PermissionError:
        flash("❌ PERMISSION DENIED: Close Courses.csv.", "error")
        return
    except Exception as e:
        flash(f"Error writing to Courses.csv: {e}", "error")
        return

    # Assign course to sections
    if target_sections:
        try:
            sections_file = data_dir / "Sections.csv"
            df = pd.read_csv(sections_file)
            for section in target_sections:
                mask = df['SectionID'] == section
                if mask.any():
                    current = str(df.loc[mask, 'Courses'].values[0])
                    if course_id not in current.split(','):
                        new_str = course_id if (pd.isna(current) or current == "") else current + "," + course_id
                        df.loc[mask, 'Courses'] = new_str
            df.to_csv(sections_file, index=False)
            flash(f"Assigned to {len(target_sections)} section(s).", "success")
        except PermissionError:
            flash("❌ PERMISSION DENIED: Close Sections.csv.", "error")
        except Exception as e:
            flash(f"Error updating sections: {e}", "error")


# --------------------------------------------------
# Main page:
# - Add course
# - Delete course
# - Run scheduler
# --------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    base_path = request.form.get("base_path", "").strip() or DEFAULT_BASE
    base = Path(base_path)

    all_sections = get_all_sections(base_path)
    all_courses = get_all_courses(base_path)

    if request.method == "POST":

        # Add new course
        if 'add_course_submit' in request.form:
            course_data = {
                "CourseID": request.form.get("new_course_id", "").strip(),
                "CourseName": request.form.get("new_course_name"),
                "Credits": int(request.form.get("new_credits")),
                "Type": request.form.get("new_type"),
                "Year": int(request.form.get("new_year")),
                "Specialization": request.form.get("new_specialization"),
                "HasLecture": 1 if request.form.get("new_has_lecture") == 'on' else 0,
                "HasLab": 1 if request.form.get("new_has_lab") == 'on' else 0,
                "IsGradProject": 1 if request.form.get("new_is_grad_project") == 'on' else 0,
            }
            selected_sections = request.form.getlist("target_sections")
            if course_data["CourseID"]:
                save_new_course(base_path, course_data, selected_sections)
            return redirect(url_for("index"))

        # Delete course
        elif 'delete_course_submit' in request.form:
            course_id = request.form.get("course_to_delete")
            selected_sections = request.form.getlist("delete_sections")
            delete_all = request.form.get("delete_all_sections") == "on"

            if course_id:
                delete_course_logic(base_path, course_id, delete_all, selected_sections)

            return redirect(url_for("index"))

        # Run scheduler
        elif 'run_scheduler_submit' in request.form:
            if not base.exists():
                flash("Base path not found.", "error")
            else:
                try:
                    result = run_scheduler(base)
                    flash("Scheduler finished.", "success")
                except Exception as e:
                    flash(f"Error: {e}", "error")

    schedule_file = Path(DEFAULT_BASE) / "timetable_sections_roomtyped.csv"

    return render_template(
        "index.html",
        default_base=DEFAULT_BASE,
        result=result,
        all_sections=all_sections,
        all_courses=all_courses,
        schedule_exists=schedule_file.exists()
    )


# --------------------------------------------------
# Download allowed output files
# --------------------------------------------------
@app.route("/download/<fname>")
def download(fname):
    if fname not in ALLOWED_OUTS:
        return "File not allowed.", 400

    base = Path(DEFAULT_BASE)
    return send_from_directory(base, fname, as_attachment=True) if (base / fname).exists() else ("File not found.", 404)


# --------------------------------------------------
# Run Flask app
# --------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
