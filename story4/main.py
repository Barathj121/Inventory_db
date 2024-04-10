import logging
from fastapi import FastAPI, HTTPException,BackgroundTasks
import psycopg2
from typing import List, Optional
from pydantic import BaseModel
from fastapi import HTTPException
from datetime import datetime,timedelta
import asyncpg
from fastapi.middleware.cors import CORSMiddleware
from passlib.hash import bcrypt  # For password hashing
from fastapi import FastAPI, HTTPException,BackgroundTasks
from pydantic import BaseModel
import string
import random
from email.mime.text import MIMEText
import os
from twilio.rest import Client
from typing import List
from dotenv import load_dotenv
import smtplib
load_dotenv('.env')

logger = logging.getLogger("uvicorn")


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
            # Step 1: Retrieve the record with the highest ID for each product from the inventory_product_history table
            cur.execute(
                """
                SELECT iph."product_id", iph."total_quantity", iph."inventory_id", iph."location"
                FROM "inventory_product_history" iph
                INNER JOIN (
                    SELECT "product_id", MAX("id") as max_id
                    FROM "inventory_product_history"
                    GROUP BY "product_id"
                ) iph_max ON iph."product_id" = iph_max."product_id" AND iph."id" = iph_max.max_id
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

class UserRegistration(BaseModel):
    name: str
    email: str
    password: str
    phone_number: str

@app.post("/register")
async def register_user(user_data: UserRegistration):
    logger.info(f"Received user data: {user_data.json()}")
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        hashed_password = bcrypt.hash(user_data.password)
        now = datetime.now()
        cur.execute(
            """
            INSERT INTO "User" ("Name", "Email", "Password_Hash", "Contact_Info", "datetime")
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_data.name, user_data.email, hashed_password, user_data.phone_number, now)
        )
        conn.commit()
        return {"status": "success"}
    except (Exception, psycopg2.Error) as error:
        print(f"Error registering user: {error}")
        return {"status": "error", "detail": str(error)}
    finally:
        if conn:
            cur.close()
            conn.close()

class UserLogin(BaseModel):
    email: str
    password: str

@app.post("/login")
async def login_user(user_data: UserLogin):
    logger.info(f"Received login data: {user_data.json()}")
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT "Password_Hash" FROM "User" WHERE "Email" = %s
            """,
            (user_data.email,)
        )
        result = cur.fetchone()
        if result is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        hashed_password = result[0]
        if not bcrypt.verify(user_data.password, hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        return {"status": "success"}
    except (Exception, psycopg2.Error) as error:
        print(f"Error logging in user: {error}")
        return {"status": "error", "detail": str(error)}
    finally:
        if conn:
            cur.close()
            conn.close()


class EmailInput(BaseModel):
    email: str

def generate_otp():
    return "".join(random.choices(string.digits, k=6))

@app.post("/send_otp")
async def send_otp(data: EmailInput):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Check if the user is registered
    cur.execute(
        """
        SELECT "Email" FROM "User" WHERE "Email" = %s
        """,
        (data.email,)
    )
    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate the OTP
    otp = generate_otp()

    # Send the OTP via email
    subject = "Password Reset OTP"
    message = f"Your OTP for resetting your password is {otp}."
    from_addr = Envs.MAIL_FROM
    password = Envs.MAIL_PASSWORD
    to_addr = data.email

    send_email(subject, message, from_addr, to_addr, password)


    # Calculate the expiry time
    expiry = datetime.now() + timedelta(minutes=5)

    # Store the OTP in the database
    cur.execute(
        """
        INSERT INTO "Otp" ("Email", "otp", "Expiration_Time") VALUES (%s, %s, %s)
        ON CONFLICT ("Email") DO UPDATE SET "otp" = %s, "Expiration_Time" = %s
        """,
        (to_addr, otp, expiry, otp, expiry)
    )
    conn.commit()

    return {"status": "success"}


class OtpInput(BaseModel):
    email: str
    otp_code: str


@app.post("/verify_otp")
async def verify_otp(data: OtpInput):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Check the OTP
    cur.execute(
        """
        SELECT "otp" FROM "Otp" WHERE "Email" = %s AND "Expiration_Time" > NOW()
        """,
        (data.email,)
    )
    result = cur.fetchone()
    if result is None or result[0] != data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    return {"status": "success"}


class ResetPasswordInput(BaseModel):
    email: str
    new_password: str


@app.post("/reset_password")
async def reset_password(data: ResetPasswordInput):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Reset the password
    hashed_password = bcrypt.hash(data.new_password)
    cur.execute(
        """
        UPDATE "User" SET "Password_Hash" = %s WHERE "Email" = %s
        """,
        (hashed_password, data.email)
    )
    conn.commit()

    return {"status": "success"}




class ReorderPoint(BaseModel):
    product_name: str
    reorder_point: int

@app.post("/reorder-points")
async def set_reorder_points(reorder_points: List[ReorderPoint]):
    conn = None
    non_existent_products = []

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        for data in reorder_points:
            # Check if the product exists
            cur.execute(
                """
                SELECT "ProductID" FROM "Product" WHERE "Product_Name" = %s
                """,
                (data.product_name,)
            )
            result = cur.fetchone()

            if result is None:
                non_existent_products.append(data.product_name)
                continue

            # If the product exists, update the reorder point
            cur.execute(
                """
                UPDATE "Product"
                SET "reorder_points" = %s
                WHERE "ProductID" = %s
                """,
                (data.reorder_point, result[0])
            )

        conn.commit()

        if non_existent_products:
            return {"status": "error", "detail": f"These products do not exist: {non_existent_products}"}

        return {"status": "success"}

    except (Exception, psycopg2.Error) as error:
        print(f"Error setting reorder points: {error}")
        return {"status": "error", "detail": str(error)}

    finally:
        if conn:
            cur.close()
            conn.close()



class Envs:
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_FROM = os.getenv('MAIL_FROM')

def send_email(subject, message, from_addr, to_addr, password):
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_addr, password)
    server.send_message(msg)
    server.quit()



class Emailinput(BaseModel):
    email: str


@app.post("/get_role")
async def get_role(data: Emailinput):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get the RoleID from the User table
    cur.execute(
        """
        SELECT "RoleID" FROM "User" WHERE "Email" = %s
        """,
        (data.email,)
    )
    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    role_id = result[0]

    # Get the Role_Name from the Role table
    cur.execute(
        """
        SELECT "Role_Name" FROM "Role" WHERE "RoleID" = %s
        """,
        (role_id,)
    )
    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Role not found")

    role_name = result[0]

    return {"role": role_name}

class ProductLocation(BaseModel):
    inventoryNo: int
    productID: int
    productName: str
    location: str
# Modify the route for fetching product locations to match the frontend endpoint
@app.get("/product-locations", response_model=List[ProductLocation])
async def get_product_locations():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        cur.execute(
         """
            SELECT ip."InventoryID", ip."product_id", p."Product_Name", ip."location"
            FROM "inventory_product" ip
            INNER JOIN "Product" p ON p."ProductID" = ip."product_id";
            """
        )
        rows = cur.fetchall()
        product_locations = []
        for row in rows:
            product_location = ProductLocation(
                inventoryNo=row[0],
                productID=row[1],
                productName=row[2],
                location=row[3]
            )
            product_locations.append(product_location)

        return product_locations

    except (Exception, psycopg2.Error) as error:
        print(f"Error fetching product locations: {error}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if conn:
            cur.close()
            conn.close()

