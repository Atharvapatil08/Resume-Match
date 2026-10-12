
import os
import re
import hashlib
from pathlib import Path

import fitz
import pandas as pd
import streamlit as st

# -------------------- PAGE SETUP --------------------
st.set_page_config(
    page_title="ORMAE TalentMatch",
    page_icon="👥",
    layout="wide"
)

st.title("ORMAE TalentMatch")
st.caption("Employee Resume & Skill Matching System")

os.makedirs("resumes", exist_ok=True)
os.makedirs("photos", exist_ok=True)

# -------------------- LOAD EMPLOYEES --------------------
try:
    df = pd.read_csv("employee.csv").fillna("")
    df.columns = df.columns.str.strip()
except Exception as e:
    st.error(f"Unable to load employee.csv: {e}")
    st.stop()

required = ["Employee_ID", "Name", "Education", "Skills"]
missing = [col for col in required if col not in df.columns]

if missing:
    st.error(f"Missing CSV columns: {', '.join(missing)}")
    st.stop()


def clean(value):
    return re.sub(r"\s+", " ", str(value)).strip()


def extract_section(text, heading):
    pattern = (
        rf"(?im)^\s*{heading}\s*:?\s*\n?"
        rf"(.*?)"
        rf"(?=^\s*(?:Education|Skills|Experience|"
        rf"Projects|Certifications?|CGPA|Achievements|"
        rf"Personal Details|Languages)\s*:?\s*$|\Z)"
    )
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def split_skills(text):
    # Split skills written on separate lines or separated by commas
    text = re.sub(r"(?i)\b(Language|Web|Database)\s*:\s*", "", text)
    items = re.split(r"[,;\n|•]+", text)
    return list(dict.fromkeys(
        clean(item).strip(" -•:")
        for item in items
        if clean(item).strip(" -•:")
    ))


def normalize(value):
    return clean(value).casefold()


def employee_skills(value):
    return {normalize(skill) for skill in split_skills(str(value))}


def photo_path(value):
    if not value:
        return None

    path = Path(str(value))
    candidates = [path, Path("photos") / path.name]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return None


# -------------------- RESUME UPLOAD --------------------
st.subheader("Upload New Resume")

uploaded_file = st.file_uploader(
    "Choose a candidate resume",
    type=["pdf"]
)

if uploaded_file:
    file_hash = hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:12]
    file_path = Path("resumes") / f"{file_hash}_{Path(uploaded_file.name).name}"
    file_path.write_bytes(uploaded_file.getvalue())

    with fitz.open(str(file_path)) as pdf:
        resume_text = "\n".join(page.get_text() for page in pdf)

    if not resume_text.strip():
        st.warning("No text found. This may be a scanned PDF.")
        st.info("Please use a text-based PDF for resume extraction.")
        st.stop()

    # Extract main resume sections
    lines = [clean(line) for line in resume_text.splitlines() if clean(line)]
    candidate_name = lines[0] if lines else "Not Found"

    education_text = extract_section(resume_text, "Education")
    skills_text = (
        extract_section(resume_text, "Skills")
        or extract_section(resume_text, "Languages")
    )

    education_lines = [
        clean(line).strip("•-")
        for line in education_text.splitlines()
        if clean(line)
    ]

    college_name = next(
        (
            line for line in education_lines
            if any(word in line.casefold()
                   for word in ["university", "college", "institute"])
        ),
        "Not Found"
    )

    degree = next(
        (
            line for line in education_lines
            if line != college_name
            and any(word in line.casefold() for word in [
                "b.tech", "bachelor", "b.sc", "b.e.", "m.tech",
                "master", "diploma", "degree", "computer science"
            ])
        ),
        "Not Found"
    )

    skill_list = split_skills(skills_text)

    # Extract key interview highlights
    experience_text = extract_section(resume_text, "Experience")
    projects_text = extract_section(resume_text, "Projects")
    certifications_text = extract_section(resume_text, "Certifications")

    highlights = []

    if experience_text:
        highlights.append(
            ("Experience", experience_text.splitlines()[0].strip())
        )

    if projects_text:
        highlights.append(
            ("Project", projects_text.splitlines()[0].strip())
        )

    if certifications_text:
        certification_lines = [
            line.strip(" •\t-")
            for line in certifications_text.splitlines()
             if line.strip(" •\t-")
         ]

        if certification_lines:
            highlights.append(
                 ("Certifications", ", ".join(certification_lines[:2]))
            )

    highlights = highlights[:3]

    # -------------------- CANDIDATE PHOTO --------------------
    uploaded_photo = st.file_uploader(
        "Upload candidate photo (optional)",
        type=["jpg", "jpeg", "png"],
        key="candidate_photo"
    )

    saved_photo = None
    if uploaded_photo:
        photo_name = f"{file_hash}_{Path(uploaded_photo.name).name}"
        saved_photo = Path("photos") / photo_name
        saved_photo.write_bytes(uploaded_photo.getvalue())

    # -------------------- HIGHLIGHTS CARD --------------------
    with st.container(border=True):
        st.subheader("Candidate Resume Highlights")

        photo_col, details_col = st.columns([1, 5])

        with photo_col:
            if saved_photo:
                st.image(str(saved_photo), width=210)
            else:
                st.markdown("### 👤")

        with details_col:
            st.markdown(f"### {candidate_name}")
            st.caption("Candidate Name")

            st.write("**Education:**", degree)

            for label, detail in highlights:
                 st.write(f"**{label}:** {detail}")

            st.caption(f"Resume: {uploaded_file.name}")

        st.divider()
        st.markdown("#### College Name")
        if college_name != "Not Found":
            if st.button(
                f"🎓 {college_name}",
                key="college_tag",
                use_container_width=False
            ):
                st.session_state["selected_match"] = (
                    "college", college_name
                )
        else:
            st.caption("College name not found in the resume.")

        st.divider()
        st.markdown("#### Skills")

        if skill_list:
            tag_cols = st.columns(4)
            for i, skill in enumerate(skill_list):
                with tag_cols[i % 4]:
                    if st.button(
                        f"🏷️ {skill}",
                        key=f"skill_{i}",
                        use_container_width=True
                    ):
                        st.session_state["selected_match"] = (
                            "skill", skill
                        )
        else:
            st.caption("No skills found in the resume.")

    # -------------------- MATCHING RESULTS --------------------
    st.subheader("Matching Results")

    selection = st.session_state.get("selected_match")

    if selection:
        match_type, selected_value = selection
        st.caption(f"Matching by: {selected_value}")

        if match_type == "college":
            matches = df[
                df["Education"].apply(normalize)
                == normalize(selected_value)
            ]
        else:
            matches = df[
                df["Skills"].apply(
                    lambda value: normalize(selected_value)
                    in employee_skills(value)
                )
            ]

        if matches.empty:
            st.info("No matching employees found.")
        else:
            st.success(f"{len(matches)} matching employee(s) found.")

            for _, employee in matches.iterrows():
                with st.container(border=True):
                    photo_col, info_col = st.columns([1, 5])

                    with photo_col:
                        image_path = (
                            photo_path(employee.get("Photo_File", ""))
                            if "Photo_File" in df.columns else None
                        )
                        if image_path:
                            st.image(image_path, width=90)
                        else:
                            st.markdown("👤")

                    with info_col:
                        st.markdown(f"**{employee['Name']}**")
                        st.caption(f"Employee ID: {employee['Employee_ID']}")
                        st.caption(f"College: {employee['Education']}")
                        st.write(f"Skills: {employee['Skills']}")
    else:
        st.info("Click a college or skill tag to find matching employees.")

else:
    st.info("Upload a PDF resume to view candidate highlights and matching tags.")
