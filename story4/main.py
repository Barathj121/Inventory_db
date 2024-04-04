from fastapi import FastAPI
import psycopg2
from typing import List, Optional
from pydantic import BaseModel
from fastapi import HTTPException
from datetime import datetime
import asyncpg
from fastapi.middleware.cors import CORSMiddleware


DATABASE_URL = "dbname=inventory_wxrq user=inventory_wxrq_user password=32T4vxi3Pe4E703IDoJFRLjLDPnVjaQ6 host=dpg-co2n9f021fec73b0s4g0-a.oregon-postgres.render.com port=5432"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

class Product(BaseModel):
    ProductID: int
    Product_Name: str

@app.get("/products")
async def get_products():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT \"ProductID\", \"Product_Name\" FROM \"Product\"")
            rows = cur.fetchall()
    return {str(row[0]): row[1] for row in rows}

# import React, { useEffect, useState } from 'react'; for frontend reference

# function ProductList() {
#   const [products, setProducts] = useState({});

#   useEffect(() => {
#     fetch('http://localhost:8000/products')
#       .then(response => response.json())
#       .then(data => setProducts(data));
#   }, []);

#   return (
#     <div>
#       {Object.entries(products).map(([productId, productName]) => (
#         <div key={productId}>
#           <h2>Product ID: {productId}</h2>
#           <p>Product Name: {productName}</p>
#         </div>
#       ))}
#     </div>
#   );
# }

# export default ProductList;

@app.get("/inventories")
async def get_inventories():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT \"InventoryID\", \"Inventory_name\" FROM \"Inventory\"")
            rows = cur.fetchall()
    return {str(row[0]): row[1] for row in rows}



from typing import List

class InventoryProduct(BaseModel):
    inventory_id: int
    product_id: int
    import_: float
    export: float
    location: str

@app.post("/inventory_product")
async def update_inventory_product(inventory_products: List[InventoryProduct]):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            for inventory_product in inventory_products:
                # Check if the product_id and inventory_id exist in the inventory_product table
                cur.execute(
                    """SELECT * FROM "inventory_product" WHERE "product_id" = %s AND "InventoryID" = %s""",
                    (inventory_product.product_id, inventory_product.inventory_id)
                )
                row = cur.fetchone()
                total_quantity = inventory_product.import_ - inventory_product.export
                if row:
                    # If the record exists, update the quantity
                    cur.execute(
                        """UPDATE "inventory_product" SET quantity = quantity + %s WHERE "product_id" = %s AND "InventoryID" = %s RETURNING quantity""",
                        (total_quantity, inventory_product.product_id, inventory_product.inventory_id)
                    )
                    total_quantity = cur.fetchone()[0]
                else:
                    # If the record does not exist, insert a new record
                    cur.execute(
                        """INSERT INTO "inventory_product" ("product_id", "InventoryID", "quantity", "location") VALUES (%s, %s, %s, %s) RETURNING quantity""",
                        (inventory_product.product_id, inventory_product.inventory_id, total_quantity, inventory_product.location)
                    )
                    total_quantity = cur.fetchone()[0]
                # Insert a new record into inventory_product_history
                cur.execute(
                    """INSERT INTO "inventory_product_history" ("product_id", "inventory_id", "datetime", "import", "export", "total_quantity", "location") VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (inventory_product.product_id, inventory_product.inventory_id, datetime.now(), inventory_product.import_, inventory_product.export, total_quantity, inventory_product.location)
                )
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

    return {"message": "Inventory updated successfully"}

    
@app.get("/recent_products")
async def get_recent_products():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            # Step 1: Retrieve the latest record for each product from the inventory_product_history table
            cur.execute(
                """
                SELECT DISTINCT ON ("product_id") "product_id", "total_quantity", "inventory_id", "location"
                FROM "inventory_product_history"
                ORDER BY "product_id", "datetime" DESC
                """
            )
            rows = cur.fetchall()

            # Step 2: Update the product_name variable by passing all the product_id's that are received
            product_ids = [row[0] for row in rows]
            cur.execute(
                """
                SELECT "ProductID", "Product_Name"
                FROM "Product"
                WHERE "ProductID" IN %s
                """,
                (tuple(product_ids),)
            )
            product_names = {product_id: product_name for product_id, product_name in cur.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

    return [{"product_id": row[0], "quantity": row[1], "inventory_id": row[2], "location": row[3], "product_name": product_names.get(row[0], "")} for row in rows]


class History(BaseModel):
    product_id: Optional[int] = None

@app.post("/view_history")
async def view_history(history: History):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            if history.product_id:
                # If product_id is provided, retrieve its history
                cur.execute(
                    """SELECT * FROM "inventory_product_history" WHERE "product_id" = %s""",
                    (history.product_id,)
                )
            else:
                # If product_id is not provided, retrieve all history
                cur.execute("""SELECT * FROM "inventory_product_history" """)
            
            rows = cur.fetchall()
            # Convert rows to JSON with column names
            result = [
                {
                    "product_id": row[0],
                    "inventory_id": row[1],
                    "datetime": row[2],
                    "import": row[3],
                    "export": row[4],
                    "location": row[5],
                    "id": row[6],
                    "total_quantity": row[7]
                }
                for row in rows
            ]
            return result
    finally:
        conn.close()
