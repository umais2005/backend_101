import pandas as pd
import asyncio
from groq import Groq
from openai import AsyncOpenAI
import os
from dataclasses import dataclass
from dotenv import load_dotenv
import supabase
from utils import get_embeddings, init_openai, init_supabase
load_dotenv()

supabase_client  = init_supabase()

# @dataclass
# class Product:
#     name: str
#     description: str
#     short_description: str
#     category: str
#     price: float
#     url_key: str
#     embeddings : list[float]
semaphore = asyncio.Semaphore(10)

async def process_and_store_product(product: pd.Series):
    async with semaphore:
        embedding = await get_embeddings(product["description"], init_openai())
        print("Got embedding for product: ", product['url_key'])
        try:
            data = {
                "name" : product['name'],
                "description" : product['description'],
                "short_description" : product['short_description'],
                "category" : product['category'],
                "price" : product['price'],
                "url_key" : product['url_key'],
                "embedding" : embedding,
            }
            supabase_client.table("products").upsert(data).execute()
            print("Inserted Succesfully product:",product['url_key'])
        except Exception as e:
            print(f"Error inserting product {product['name']}: {e}")
        

async def main(start, end=None):
    df = pd.read_csv("products_cleaned.csv")

    tasks = []
    if end is None:
        end = len(df)
    df = df.iloc[start:end]
    for index, row in df.iterrows():
        task = asyncio.create_task(process_and_store_product(row))
        tasks.append(task)
        # if len(tasks) >= :
        #     break
        
    await asyncio.gather(*tasks)

asyncio.run(main(1523))