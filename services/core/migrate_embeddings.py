"""
Migrate patterns to add embeddings
"""
import asyncio
import json
from sqlalchemy import text
from database import AsyncSessionLocal
from semantic.embedding_service import embed_text

async def migrate():
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT id, pattern_id, skill_sequence, goal_text 
            FROM skill_patterns 
            WHERE embedding IS NULL
        """)
        result = await session.execute(query)
        rows = result.fetchall()
        print(f"Migrating {len(rows)} patterns...", flush=True)
        
        for row in rows:
            pattern_id = row[0]
            p_id = row[1]
            skill_seq = row[2]
            existing_text = row[3]
            
            if isinstance(skill_seq, list):
                skills = skill_seq
            else:
                try:
                    skills = json.loads(skill_seq) if skill_seq else []
                except:
                    skills = [skill_seq] if skill_seq else []
            
            if existing_text:
                emb_text = existing_text
            else:
                skills_str = " -> ".join(str(s) for s in skills) if skills else "unknown"
                emb_text = f"Execution pipeline with {len(skills)} steps: {skills_str}"
            
            embedding = embed_text(emb_text)
            
            if embedding:
                emb_json = json.dumps(embedding)
                emb_text_escaped = emb_text.replace("'", "''")
                
                sql = f"""
                    UPDATE skill_patterns 
                    SET embedding = '{emb_json}'::jsonb,
                        goal_text = COALESCE('{emb_text_escaped}', goal_text)
                    WHERE id = '{pattern_id}'
                """
                await session.execute(text(sql))
                print(f"  + {p_id[:40]}... ({len(skills)} skills)", flush=True)
            else:
                print(f"  - {p_id}: embedding failed", flush=True)
        
        await session.commit()
        print("Done!", flush=True)

if __name__ == "__main__":
    asyncio.run(migrate())
