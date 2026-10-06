with open("/Users/apple/Desktop/FLA/automation_engine/api/main.py", "r") as f:
    content = f.read()

# Replace the pause with auto-export
old_pause = """        # Store for review
        task.extracted_data = extracted_data
        task.status = "review_needed"
        task.logs += "[+] Ready for human review.\\n"
        db.commit()"""

new_auto_export = """        task.logs += "[*] Stage 5: Exporting to Excel...\\n"
        db.commit()
        
        output_dir = os.path.join(BASE_OUTPUT_DIR, task_id)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "FLA_Return_Populated.xlsx")

        engine_dir = os.path.dirname(os.path.abspath(__file__))
        skeletal_path = os.path.abspath(os.path.join(engine_dir, "..", "..", "excel", "FLA Return existing skeletal.xlsx"))
        
        writer = ExcelWriter(skeletal_path, output_path)
        writer.write_values(target_cells)
        
        task.logs += "[*] Stage 6: Running Validations...\\n"
        db.commit()
        validator = ReturnValidator()
        validator.run_all_checks(target_cells)
        validator.save_report(output_dir)
        
        task.extracted_data = extracted_data
        task.status = "completed"
        task.output_excel = output_path
        task.completed_at = datetime.utcnow()
        task.logs += "[+] Pipeline finished successfully.\\n"
        db.commit()"""

content = content.replace(old_pause, new_auto_export)

with open("/Users/apple/Desktop/FLA/automation_engine/api/main.py", "w") as f:
    f.write(content)
