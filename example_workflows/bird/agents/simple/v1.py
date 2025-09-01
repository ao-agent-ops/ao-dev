#!/usr/bin/env python3
import argparse
import json
import sqlite3
import openai
from tqdm import tqdm
import os

openai.debug=True
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_db_schema(db_path: str, num_rows: int = 3) -> str:
    """
    Generate schema prompt with example rows for each table
    """
    schema_prompts = []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for table in tables:
        if table[0] == 'sqlite_sequence':
            continue
            
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table[0]}'")
        create_statement = cursor.fetchone()[0]
        schema_prompts.append(create_statement)
        
        table_name = table[0]
        if table_name in ['order', 'by', 'group']:
            table_name = f"`{table_name}`"
            
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {num_rows}")
        rows = cursor.fetchall()
        
        if rows:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
            columns = [description[0] for description in cursor.description]
            
            example_rows = f"\n/* {num_rows} example rows from {table_name}:\n"
            example_rows += " | ".join(columns) + "\n"
            for row in rows:
                example_rows += " | ".join(str(val) if val is not None else "NULL" for val in row) + "\n"
            example_rows += "*/"
            schema_prompts.append(example_rows)
    
    conn.close()
    return "\n\n".join(schema_prompts)


def generate_sql_with_gpt4o_mini(question: str, schema: str, evidence: str = None) -> str:
    """
    Use GPT-4o-mini to generate SQL query
    """
    system_prompt = """You are an expert SQL query generator for SQLite databases. 
    Generate precise SQL queries based on the given schema and question.
    Return ONLY the SQL query without any explanation or markdown formatting."""
    
    user_prompt = f"""Database Schema:
{schema}

{"External Knowledge: " + evidence if evidence else ""}

Question: {question}

Generate a SQL query to answer this question. Return ONLY the SQL query."""

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0,
        max_tokens=256
    )
    
    sql = response.choices[0].message.content.strip()
    
    # Clean up the SQL if it has markdown formatting
    if sql.startswith("```"):
        sql = sql.split("```")[1]
        if sql.startswith("sql"):
            sql = sql[3:].strip()
    if sql.endswith("```"):
        sql = sql[:-3].strip()
    
    # Ensure it starts with SELECT if it doesn't
    if not sql.upper().startswith("SELECT"):
        sql = "SELECT " + sql
        
    return sql


def process_bird_dataset(data_path: str, db_root_path: str, output_path: str, mode: str = 'dev', num_questions: int = None):
    """
    Process BIRD dataset and generate predictions
    """    
    # Load the dataset
    with open(data_path, 'r') as f:
        data = json.load(f)
    
    # In test mode, only process first num_questions questions
    if num_questions:
        data = data[:num_questions]
        print(f"NOTE: Processing only first {num_questions} questions")
    
    predictions = {}
    
    print(f"Processing {len(data)} questions...")
    
    for idx, item in enumerate(tqdm(data)):
        question = item['question']
        db_id = item['db_id']
        evidence = item.get('evidence', '')
        
        # Construct database path
        # Check if db_root_path already includes the database subdirectory
        if os.path.exists(f"{db_root_path}/{db_id}/{db_id}.sqlite"):
            db_path = f"{db_root_path}/{db_id}/{db_id}.sqlite"
        elif os.path.exists(f"{db_root_path}/dev_databases/{db_id}/{db_id}.sqlite"):
            db_path = f"{db_root_path}/dev_databases/{db_id}/{db_id}.sqlite"
        else:
            db_path = f"{db_root_path}/{db_id}/{db_id}.sqlite"
            print(f"Warning: Database path may not exist: {db_path}")
        
        try:
            # Get database schema
            schema = get_db_schema(db_path)
            
            # Generate SQL using GPT-4o-mini
            sql = generate_sql_with_gpt4o_mini(question, schema, evidence)
            
            # Format output as expected by BIRD evaluation
            # Format: "SQL\t----- bird -----\tdb_name"
            formatted_output = f"{sql}\t----- bird -----\t{db_id}"
            predictions[str(idx)] = formatted_output
            
        except Exception as e:
            import traceback
            print(f"\n=== Error processing question {idx} ===")
            print(f"Question: {question[:100]}...")
            print(f"DB ID: {db_id}")
            print(f"DB Path: {db_path}")
            print(f"Error: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            # Provide a default query on error
            predictions[str(idx)] = f"SELECT 1\t----- bird -----\t{db_id}"
    
    # Save predictions to file
    output_file = f"{output_path}/predict_{mode}.json"
    with open(output_file, 'w') as f:
        json.dump(predictions, f, indent=4)
    
    print(f"Predictions saved to {output_file}")
    return predictions


def main():
    parser = argparse.ArgumentParser(description='Simple Text-to-SQL Agent for BIRD Benchmark')
    parser.add_argument('--data_path', type=str, required=True, 
                        help='Path to BIRD dataset JSON file')
    parser.add_argument('--db_root_path', type=str, required=True,
                        help='Root path to BIRD databases')
    parser.add_argument('--output_path', type=str, required=True,
                        help='Output directory for predictions')
    parser.add_argument('--mode', type=str, default='dev',
                        choices=['dev', 'test'],
                        help='Evaluation mode (dev or test)')
    parser.add_argument('--num_questions', type=int, default=None,
                        help='Only process first n questions, default is None (all questions)')
    
    args = parser.parse_args()
    
    process_bird_dataset(
        data_path=args.data_path,
        db_root_path=args.db_root_path,
        output_path=args.output_path,
        mode=args.mode,
        num_questions=args.num_questions,
    )


if __name__ == '__main__':
    main()