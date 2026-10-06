import os
import re
import datetime
import streamlit as st
import pandas as pd
from config.db import fetch_image_data, save_to_image_data, delete_image_data, update_image_data, format_tags

st.title("📌 Notes & Image Log")
st.markdown("Manage your notes and trade charts/images. Click **Add Note** to upload images and record notes.")
st.divider()

# Ensure upload directory exists
UPLOAD_DIR = "upload"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def parse_tag_tokens(raw_tags_str) -> list:
    """Extract clean list of tag strings from a space or semicolon separated raw string."""
    if not raw_tags_str or pd.isna(raw_tags_str) or not str(raw_tags_str).strip():
        return []
    return [t.strip() for t in re.split(r'[\s;]+', str(raw_tags_str)) if t.strip()]


@st.dialog("Add Note", width="large")
def add_note_dialog():
    st.write("Fill in the details below to save a new note.")
    
    with st.form("add_note_form", clear_on_submit=False):
        left_col, right_col = st.columns(2)
        
        with left_col:
            note_text = st.text_area(
                "Note", 
                placeholder="Enter your note or trade observation here...",
                height=140,
                help="Text contents for the note"
            )

            solution_text = st.text_area(
                "Solution",
                placeholder="Enter solution or key takeaway...",
                height=140,
                help="Solution or resolution details for this note"
            )

        with right_col:
            uploaded_image = st.file_uploader(
                "Upload Image", 
                type=["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"],
                help="Select an image file (PNG, JPG, JPEG, WEBP, GIF, etc.)"
            )

            tags_text = st.text_input(
                "Tags",
                placeholder="e.g. breakout nifty; swing (separated by spaces or semicolons)",
                help="Tags will be formatted automatically with semicolons"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                note_date = st.date_input("Date", value=datetime.date.today())
            with col2:
                repeat_val = st.number_input("Repeat", min_value=0, value=0, step=1, help="Repeat value or count")
            
        submitted = st.form_submit_button("💾 Save Note", use_container_width=True, type="primary")
        
        if submitted:
            if not note_text.strip() and not solution_text.strip() and not tags_text.strip() and uploaded_image is None:
                st.error("Please enter a note, solution, tags, or upload an image file.")
            else:
                image_path = None
                if uploaded_image is not None:
                    try:
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_name = "".join(c for c in uploaded_image.name if c.isalnum() or c in "._-")
                        filename = f"{timestamp}_{safe_name}"
                        full_save_path = os.path.join(UPLOAD_DIR, filename)
                        
                        with open(full_save_path, "wb") as f:
                            f.write(uploaded_image.getbuffer())
                            
                        image_path = full_save_path
                    except Exception as e:
                        st.error(f"Failed to save uploaded image: {e}")
                        st.stop()

                try:
                    save_to_image_data(
                        note=note_text.strip() if note_text else None,
                        image_path=image_path,
                        note_date=note_date,
                        repeat_val=repeat_val,
                        solution=solution_text.strip() if solution_text else None,
                        tags=tags_text.strip() if tags_text else None
                    )
                    st.success("Note added successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving to database: {e}")


@st.dialog("Update Note", width="large")
def update_note_dialog(note_id: int, current_note: str, current_solution: str, current_tags: str, current_img_path: str, current_date, current_repeat: int):
    st.write(f"Update details for Note #{note_id}")
    
    # Parse existing date
    init_date = datetime.date.today()
    if current_date and pd.notna(current_date):
        try:
            init_date = pd.to_datetime(current_date).date()
        except Exception:
            pass

    with st.form(f"update_note_form_{note_id}", clear_on_submit=False):
        left_col, right_col = st.columns(2)
        
        with left_col:
            updated_note = st.text_area("Note", value=current_note or "", height=140, placeholder="Update your note text...")
            updated_solution = st.text_area("Solution", value=current_solution or "", height=140, placeholder="Update solution details...")
            
        with right_col:
            st.write("**Image:**")
            if current_img_path and pd.notna(current_img_path) and str(current_img_path).strip() != "":
                st.caption(f"Current image: `{current_img_path}`")
                if os.path.exists(current_img_path):
                    st.image(current_img_path, width=200)
                remove_img = st.checkbox("Remove existing image", key=f"rm_img_{note_id}")
            else:
                remove_img = False

            uploaded_new_image = st.file_uploader(
                "Upload New Image (optional)",
                type=["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"],
                key=f"new_img_{note_id}"
            )

            updated_tags = st.text_input("Tags", value=current_tags or "", placeholder="e.g. breakout nifty; swing")

            col1, col2 = st.columns(2)
            with col1:
                updated_date = st.date_input("Date", value=init_date, key=f"date_{note_id}")
            with col2:
                updated_repeat = st.number_input(
                    "Repeat", 
                    min_value=0, 
                    value=int(current_repeat) if pd.notna(current_repeat) else 0, 
                    step=1,
                    key=f"repeat_{note_id}"
                )

        submitted = st.form_submit_button("💾 Update Note", use_container_width=True, type="primary")

        if submitted:
            final_img_path = current_img_path
            
            if remove_img:
                final_img_path = ""
                if current_img_path and os.path.exists(current_img_path):
                    try:
                        os.remove(current_img_path)
                    except Exception:
                        pass

            if uploaded_new_image is not None:
                try:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = "".join(c for c in uploaded_new_image.name if c.isalnum() or c in "._-")
                    filename = f"{timestamp}_{safe_name}"
                    full_save_path = os.path.join(UPLOAD_DIR, filename)

                    with open(full_save_path, "wb") as f:
                        f.write(uploaded_new_image.getbuffer())

                    final_img_path = full_save_path
                except Exception as e:
                    st.error(f"Failed to save new image: {e}")
                    st.stop()

            try:
                update_image_data(
                    note_id=note_id,
                    note=updated_note.strip() if updated_note else "",
                    image_path=final_img_path,
                    note_date=updated_date,
                    repeat_val=updated_repeat,
                    solution=updated_solution.strip() if updated_solution else "",
                    tags=updated_tags.strip() if updated_tags else ""
                )
                st.success("Note updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update note: {e}")


@st.dialog("Delete Note", width="large")
def delete_note_dialog(note_id: int, note_summary: str, image_path: str):
    st.warning(f"Are you sure you want to delete Note #{note_id}?")
    if note_summary:
        st.write(f"**Note:** {note_summary[:100]}")
    if image_path:
        st.write(f"**ImagePath:** `{image_path}`")
        
    col_del1, col_del2 = st.columns(2)
    with col_del1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            try:
                delete_image_data(note_id)
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as fe:
                        st.warning(f"Note deleted from database, but could not remove file: {fe}")
                st.success("Note deleted successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete note: {e}")
    with col_del2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


# Fetch Notes Data from Database
with st.spinner("Fetching notes from database..."):
    try:
        notes_df = fetch_image_data()
    except Exception as e:
        st.error(f"Error fetching notes from database: {e}")
        notes_df = pd.DataFrame()

# Build list of all unique tags for filter
all_unique_tags = []
if not notes_df.empty and "Tags" in notes_df.columns:
    tag_set = set()
    for raw_t in notes_df["Tags"].dropna():
        tag_set.update(parse_tag_tokens(raw_t))
    all_unique_tags = sorted(list(tag_set))

# Top Action & Filter Controls
col_btn, col_search, col_tags_filter = st.columns([2, 3, 3])

with col_btn:
    if st.button("➕ Add Note", type="primary", use_container_width=True):
        add_note_dialog()

with col_search:
    search_query = st.text_input("🔍 Search notes...", placeholder="Type keywords to filter...", label_visibility="collapsed")

with col_tags_filter:
    selected_filter_tags = st.multiselect(
        "🏷️ Filter by Tags",
        options=all_unique_tags,
        placeholder="Filter by tags (must contain all)...",
        label_visibility="collapsed"
    )

st.divider()

if notes_df.empty:
    st.info("No notes found in database. Click **Add Note** above to create your first note!")
else:
    # Filter notes by search query and selected tags
    filtered_df = notes_df.copy()
    
    if search_query:
        query = search_query.lower()
        filtered_df = filtered_df[
            filtered_df["Note"].astype(str).str.lower().str.contains(query, na=False) |
            (filtered_df["Solution"].astype(str).str.lower().str.contains(query, na=False) if "Solution" in filtered_df.columns else False) |
            (filtered_df["Tags"].astype(str).str.lower().str.contains(query, na=False) if "Tags" in filtered_df.columns else False) |
            filtered_df["ImagePath"].astype(str).str.lower().str.contains(query, na=False) |
            filtered_df["Date"].astype(str).str.lower().str.contains(query, na=False)
        ]

    # Tag filter: note MUST contain ALL selected tags
    if selected_filter_tags and "Tags" in filtered_df.columns:
        def row_contains_all_tags(row_tags_val):
            card_tags = set(parse_tag_tokens(row_tags_val))
            return all(sel_tag in card_tags for sel_tag in selected_filter_tags)
        
        filtered_df = filtered_df[filtered_df["Tags"].apply(row_contains_all_tags)]

    st.write(f"Showing **{len(filtered_df)}** note(s)")

    # Card Grid View
    cols_per_row = 3
    for row_idx in range(0, len(filtered_df), cols_per_row):
        cols = st.columns(cols_per_row)
        batch = filtered_df.iloc[row_idx : row_idx + cols_per_row]
        
        for col_idx, (_, note_row) in enumerate(batch.iterrows()):
            with cols[col_idx]:
                note_id = int(note_row.get("Id"))
                note_body = note_row.get("Note")
                solution_body = note_row.get("Solution") if "Solution" in note_row else None
                tags_body = note_row.get("Tags") if "Tags" in note_row else None
                img_path = note_row.get("ImagePath")
                note_date = note_row.get("Date")
                repeat_num = int(note_row.get("Repeat")) if pd.notna(note_row.get("Repeat")) else 0
                
                card_tag_tokens = parse_tag_tokens(tags_body)

                with st.container(border=True):
                    # Header: Date & Action Icons (Edit / Delete)
                    header_col1, header_col2, header_col3 = st.columns([4, 1, 1])
                    with header_col1:
                        st.caption(f"📅 **{note_date if pd.notna(note_date) else 'No Date'}**")
                    with header_col2:
                        if st.button("✏️", key=f"edit_{note_id}", help="Edit / Update Note"):
                            update_note_dialog(
                                note_id=note_id,
                                current_note=str(note_body or ""),
                                current_solution=str(solution_body or ""),
                                current_tags=str(tags_body or ""),
                                current_img_path=str(img_path or ""),
                                current_date=note_date,
                                current_repeat=repeat_num
                            )
                    with header_col3:
                        if st.button("🗑️", key=f"del_{note_id}", help="Delete Note"):
                            delete_note_dialog(note_id, str(note_body or ""), str(img_path or ""))
                    
                    # Image Display
                    if img_path and pd.notna(img_path) and str(img_path).strip() != "":
                        if os.path.exists(img_path):
                            st.image(img_path, use_container_width=True)
                        else:
                            st.info(f"🖼️ Path: `{img_path}` (File missing locally)")
                    
                    # Note Content
                    if note_body and pd.notna(note_body):
                        st.markdown(f"**Note:** {note_body}")
                    else:
                        st.caption("*No text note provided*")

                    # Solution Content
                    if solution_body and pd.notna(solution_body) and str(solution_body).strip() != "":
                        st.success(f"💡 **Solution:** {solution_body}")

                    # Tags Badges Display
                    if card_tag_tokens:
                        badges_html = " ".join([
                            f"<span style='background-color: {'#1976d2' if (selected_filter_tags and t in selected_filter_tags) else '#2e3b4e'}; color: #ffffff; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 500; display: inline-block; margin: 2px;'>🏷️ {t}</span>"
                            for t in card_tag_tokens
                        ])
                        st.markdown(badges_html, unsafe_allow_html=True)
                    
                    st.divider()

                    # Inline Repeat Counter (+ / -) Control
                    c_lbl, c_minus, c_cnt, c_plus = st.columns([3, 1, 2, 1])
                    with c_lbl:
                        st.markdown("**Repeat:**")
                    with c_minus:
                        if st.button("➖", key=f"dec_{note_id}", help="Decrease Repeat"):
                            new_val = max(0, repeat_num - 1)
                            update_image_data(note_id=note_id, repeat_val=new_val)
                            st.rerun()
                    with c_cnt:
                        st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1rem; padding-top: 4px;'>{repeat_num}</div>", unsafe_allow_html=True)
                    with c_plus:
                        if st.button("➕", key=f"inc_{note_id}", help="Increase Repeat"):
                            new_val = repeat_num + 1
                            update_image_data(note_id=note_id, repeat_val=new_val)
                            st.rerun()
