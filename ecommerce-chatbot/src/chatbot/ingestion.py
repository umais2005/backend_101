import pandas as pd
import asyncio
from dataclasses import dataclass
from dotenv import load_dotenv
from src.utils import get_embeddings, init_openai, init_supabase
load_dotenv()

supabase_client  = init_supabase()

@dataclass
class Product:
    name: str
    description: str
    short_description: str
    category: str
    price: float
    url_key: str
    embedding : list[float]
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
            product = Product(**data) # To validate the data
            supabase_client.table("products").upsert(product.to_dict()).execute()
            print("Inserted Succesfully product:",product['url_key'])
        except Exception as e:
            print(f"Error inserting product {product['name']}: {e}")
        

async def main(df, start, end=None):
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

if __name__ == "__main__":
        
    df = pd.read_csv("products_cleaned.csv")

    asyncio.run(main(df))