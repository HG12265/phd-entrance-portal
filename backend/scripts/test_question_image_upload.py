import os
import io
import sys
import uuid
import pandas as pd
from PIL import Image
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage

# Ensure backend/ is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.database import SessionLocal
from app.models.department import Department
from app.models.question import Question
from app.routes.question_routes import upload_questions
from app.utils.image_converter import convert_image_bytes_to_png

def create_sample_png_bytes(color='red', size=(100, 100)):
    buf = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(buf, format='PNG')
    return buf.getvalue()

def generate_test_excel_file(filepath):
    wb = Workbook()
    ws = wb.active
    ws.title = "Questions"

    # Header row
    headers = ["Question No", "Question Text", "Option A", "Option B", "Option C", "Option D", "Correct Option", "Marks"]
    ws.append(headers)

    # 70 questions
    for i in range(1, 71):
        if i == 1:
            # Q1: Text + Question Image (EMF/WMF mock)
            ws.append([1, "What is shown in the image below?", "Red Box", "Blue Circle", "Green Triangle", "Yellow Square", "A", 1])
        elif i == 2:
            # Q2: Options with images
            ws.append([2, "Select the red option diagram:", "", "", "Option C Text", "Option D Text", "A", 1])
        elif i == 3:
            # Q3: Multiple images in single cell
            ws.append([3, "Compare diagram 1 and diagram 2:", "Option A", "Option B", "Option C", "Option D", "B", 1])
        elif i == 4:
            # Q4: Image-only question AND image-only option
            ws.append([4, "", "", "Text Option B", "Text Option C", "Text Option D", "A", 1])
        else:
            ws.append([i, f"Question text number {i}", f"Option A for Q{i}", f"Option B for Q{i}", f"Option C for Q{i}", f"Option D for Q{i}", "A", 1])

    # Add images to worksheet using openpyxl
    # 1. Image for Q1 (Row 2, Col B / col index 1)
    img1_bytes = create_sample_png_bytes('purple', (120, 80))
    img1 = OpenpyxlImage(io.BytesIO(img1_bytes))
    img1.anchor = "B2"
    ws.add_image(img1)

    # 2. Image for Q2 Option A (Row 3, Col C / col index 2)
    img2_bytes = create_sample_png_bytes('red', (100, 100))
    img2 = OpenpyxlImage(io.BytesIO(img2_bytes))
    img2.anchor = "C3"
    ws.add_image(img2)

    # 3. Image for Q2 Option B (Row 3, Col D / col index 3)
    img3_bytes = create_sample_png_bytes('blue', (100, 100))
    img3 = OpenpyxlImage(io.BytesIO(img3_bytes))
    img3.anchor = "D3"
    ws.add_image(img3)

    # 4 & 5. Multiple images for Q3 (Row 4, Col B / col index 1)
    img4_bytes = create_sample_png_bytes('green', (80, 80))
    img4 = OpenpyxlImage(io.BytesIO(img4_bytes))
    img4.anchor = "B4"
    ws.add_image(img4)

    img5_bytes = create_sample_png_bytes('orange', (80, 80))
    img5 = OpenpyxlImage(io.BytesIO(img5_bytes))
    img5.anchor = "B4"
    ws.add_image(img5)

    # 6. Image-only for Q4 Question Text (Row 5, Col B)
    img6_bytes = create_sample_png_bytes('cyan', (150, 100))
    img6 = OpenpyxlImage(io.BytesIO(img6_bytes))
    img6.anchor = "B5"
    ws.add_image(img6)

    # 7. Image-only for Q4 Option A (Row 5, Col C)
    img7_bytes = create_sample_png_bytes('magenta', (90, 90))
    img7 = OpenpyxlImage(io.BytesIO(img7_bytes))
    img7.anchor = "C5"
    ws.add_image(img7)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    wb.save(filepath)
    print(f"[PASS] Created test Excel file with 70 questions and embedded cell images at: {filepath}")

def run_test():
    print("==================================================")
    print("Testing Excel Question Upload with Advanced Images")
    print("==================================================")

    db = SessionLocal()
    try:
        # Get or create active department
        dept = db.query(Department).filter(Department.is_active == True).first()
        if not dept:
            dept = Department(department_name="Test Department", department_code="TEST01", is_active=True)
            db.add(dept)
            db.commit()
            db.refresh(dept)
            
        dept_id = dept.id
        print(f"Using target department: ID={dept_id}, Name={dept.department_name}")

        test_excel_path = os.path.join("uploads", "test_question_images.xlsx")
        generate_test_excel_file(test_excel_path)

        # Mock FastAPI UploadFile
        class MockFile:
            def __init__(self, path):
                self.filename = os.path.basename(path)
                self.file = open(path, "rb")

        mock_upload = MockFile(test_excel_path)

        class MockAdmin:
            id = 1
            role = "super_admin"

        # Call upload_questions route directly
        res = upload_questions(
            department_id=dept_id,
            replace_existing=True,
            file=mock_upload, # type: ignore
            db=db,
            current_admin=MockAdmin() # type: ignore
        )

        mock_upload.file.close()

        print("\n--- Route Response Summary ---")
        print("Message:", res.message)
        print("Success Count:", res.success_count)
        print("Failed Count:", res.failed_count)

        assert res.success_count == 70, f"Expected 70 valid questions, got {res.success_count}"
        print("[PASS] Exactly 70 questions passed validation!")

        # Verify Q1 to Q4 in database
        q1 = db.query(Question).filter(Question.department_id == dept_id, Question.question_no == 1, Question.is_active == True).first()
        q2 = db.query(Question).filter(Question.department_id == dept_id, Question.question_no == 2, Question.is_active == True).first()
        q3 = db.query(Question).filter(Question.department_id == dept_id, Question.question_no == 3, Question.is_active == True).first()
        q4 = db.query(Question).filter(Question.department_id == dept_id, Question.question_no == 4, Question.is_active == True).first()

        assert q1 and "<img src=" in q1.question_text, "Q1 should contain embedded question image tag"
        print("[PASS] Requirement 1 & General Images: Q1 image extracted and embedded correctly in question_text.")

        assert q2 and "<img src=" in q2.option_a and "<img src=" in q2.option_b, "Q2 should contain embedded option image tags in Option A and Option B"
        print("[PASS] Requirement 2 (Option Images): Q2 Option A and Option B contain extracted image tags.")

        assert q3 and q3.question_text.count("<img src=") >= 2, "Q3 should contain multiple image tags in single cell"
        print("[PASS] Requirement 3 (Multiple Images in Single Cell): Q3 contains multiple image tags in question_text.")

        assert q4 and "<img src=" in q4.question_text and "<img src=" in q4.option_a, "Q4 should accept image-only question text and option A"
        print("[PASS] Requirement 4 (Image-Only Cells): Q4 image-only question text and option A accepted successfully.")

        print("\n==================================================")
        print("ALL VERIFICATION TESTS PASSED SUCCESSFULLY! 🎉")
        print("==================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_test()
