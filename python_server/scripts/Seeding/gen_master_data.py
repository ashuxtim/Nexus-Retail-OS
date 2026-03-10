#!/usr/bin/env python3
"""
gen_master_data.py  —  NexusRetailOS 10-Year Seed  (Step 1 of 3)
Generates: 5,000 products (~7,500 variants), 10,000 customers, 1,000 suppliers
Exports:   nexus_seed_maps.json   (read by gen_transactions.py)
           nexus_seed_meta.json   (human-readable summary)

Run standalone:  python gen_master_data.py
Or via master:   from gen_master_data import main; main()
"""

import os, sys, json, sqlite3, time, math
import numpy as np
from datetime import datetime
from itertools import product as iproduct

# ═══════════════════════════════════════════════════════════════════════════
#  PATH RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════
if "NEXUS_USER_DATA" in os.environ:
    BASE_DIR = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    BASE_DIR = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")

DB_PATH   = os.path.join(BASE_DIR, "nexus.db")
MAPS_PATH = os.path.join(BASE_DIR, "nexus_seed_maps.json")
META_PATH = os.path.join(BASE_DIR, "nexus_seed_meta.json")

RNG_SEED         = 42
TARGET_PRODUCTS  = 5000
TARGET_CUSTOMERS = 10000
TARGET_SUPPLIERS = 1000

# ═══════════════════════════════════════════════════════════════════════════
#  PRODUCT CATALOG  — brand × line = unique product name
#  Each category has: brands[], lines[], sizes[(name,multiplier)],
#                     price_range(min,max), unit, target_count
# ═══════════════════════════════════════════════════════════════════════════
CATALOG = {
    "Snacks": {
        "brands": [
            "Lays","Kurkure","Bingo","Uncle Chips","Haldiram","Bikaji","Balaji",
            "Parle Wafers","Doritos","Act II","Crax","Cheetos","Too Yumm",
            "Ding Dong","Fun Flips","Pringles","Yellow Diamond","Cornitos",
            "Jabsons","Bikano","Gopal Snacks","Ratlami Snacks","Prakash Namkeen",
            "Shalimar Namkeen","Anand Namkeen","Ganesh Farsan","Evergreen Wafers",
            "Madhur Namkeen","Chitale Bandhu","Ambika Papad",
        ],
        "lines": [
            "Classic Salted","Masala Munch","Cream Onion","Magic Masala",
            "Tomato Tango","Peri Peri","Pudina Fresh","Spicy Treat","Chaat Masala",
            "Tangy Tomato","Sour Cream Onion","Lime Chili","Bhujia Mix",
            "Moong Dal Fried","Aloo Bhujia","Chivda Premium","Mixed Namkeen",
            "Sev Gathiya","Mathi Flaky","Khakhra Jeera","Rice Cracker Spicy",
            "Corn Puff Masala","Ring Masala","Stix Spicy","Wafer Salted",
            "Chatpata Crunch","Methi Mathri","Masala Peanut","Roasted Chana",
        ],
        "sizes": [
            ("26g Pack",  10.0, 0.7),
            ("52g Pack",  20.0, 1.4),
            ("90g Pack",  30.0, 2.5),
            ("160g Pack", 55.0, 4.5),
        ],
        "base_prices": (10, 60),
        "unit": "Pack",
        "target": 650,
        "fast_mover_keywords": ["lays","kurkure","bingo","haldiram","bikaji","doritos"],
    },
    "Beverages": {
        "brands": [
            "Coca Cola","Pepsi","Sprite","Thums Up","Fanta","Limca","Maaza",
            "Frooti","Slice","Appy Fizz","Mountain Dew","7Up","Miranda","Real",
            "Paper Boat","Tropicana","Bisleri","Kinley","Aquafina","Red Bull",
            "Monster","Sting","Rasna","Rooh Afza","B Natural","Minute Maid",
            "Pulpy Orange","Aam Panna","Jaljeera","Nannari","Bovonto","Limca Soda",
            "Torino","Duke Soda","Goldspot",
        ],
        "lines": [
            "Regular","Diet Zero","Sparkling Water","Tonic Water","Mango Flavour",
            "Orange Flavour","Lemon Lime","Cola Original","Apple Fizz",
            "Mixed Fruit","Guava Delight","Litchi","Kokum","Tamarind",
            "Pineapple Burst","Strawberry","Mint Lime","Watermelon","Berry Mix",
            "Ginger Ale","Energy Original","Energy Berry",
        ],
        "sizes": [
            ("200ml Tetrapack", 15.0, 0.5),
            ("330ml Can",       40.0, 1.0),
            ("500ml Bottle",    45.0, 1.3),
            ("600ml Bottle",    50.0, 1.5),
            ("1.5L Bottle",     80.0, 3.5),
            ("2L Bottle",       95.0, 5.0),
        ],
        "base_prices": (15, 50),
        "unit": "Bottle",
        "target": 700,
        "fast_mover_keywords": ["coca cola","pepsi","sprite","thums up","frooti","maaza","bisleri","7up","mountain dew"],
    },
    "Dairy": {
        "brands": [
            "Amul","Mother Dairy","Nestle","Parag","Verka","Gowardhan",
            "Heritage","Milma","Aavin","Nandini","Vijaya","Dodla",
            "Prabhat","Saras","Mehsana","Mahananda","Kwality Dairy",
            "Srikhand Brand","Ananda","Arokya",
        ],
        "lines": [
            "Full Cream Milk","Toned Milk","Double Toned Milk","Skimmed Milk",
            "Butter Salted","Butter Unsalted","Pure Ghee","Fresh Paneer",
            "Set Curd","Fruit Yoghurt","Strawberry Yoghurt","Plain Lassi",
            "Sweet Lassi","Masala Chaas","Cheese Slices","Processed Cheese",
            "Fresh Cream","Condensed Milk","Shrikhand Kesar","Khoa Fresh",
        ],
        "sizes": [
            ("200ml Pouch",  22.0, 0.5),
            ("500ml Pouch",  30.0, 1.0),
            ("1L Pack",      58.0, 2.0),
            ("200g Pack",    50.0, 1.0),
            ("500g Pack",   100.0, 2.0),
        ],
        "base_prices": (22, 120),
        "unit": "Pack",
        "target": 300,
        "fast_mover_keywords": ["amul","mother dairy","amul butter","amul milk"],
    },
    "Bakery": {
        "brands": [
            "Britannia","Parle","Sunfeast","Priyagold","Anmol","Dukes",
            "Cremica","McVities","Bonn","Harvest Gold","Modern Bread",
            "English Oven","Bakers Pride","Wibs","Monginis",
        ],
        "lines": [
            "Marie Gold","Glucose Biscuit","Butter Cookies","Cream Sandwich",
            "Digestive","Oat Cracker","Coconut Cookies","Chocolate Chip",
            "Multigrain Biscuit","Atta Biscuit","Salt Cracker","Cheese Cracker",
            "Brown Bread Loaf","White Bread Loaf","Multigrain Bread","Whole Wheat Bread",
            "Cake Rusk","Plain Rusk","Milk Rusk","Khari Biscuit",
            "Puff Pastry","Cream Roll","Nut Cookies","Bourbon Chocolate",
            "Good Day Cashew","Treat Cream","Tiger Glucose",
        ],
        "sizes": [
            ("60g Pack",   12.0, 0.5),
            ("150g Pack",  30.0, 1.2),
            ("250g Pack",  45.0, 2.0),
            ("400g Pack",  80.0, 3.5),
        ],
        "base_prices": (12, 100),
        "unit": "Pack",
        "target": 400,
        "fast_mover_keywords": ["britannia","parle","good day","marie"],
    },
    "Instant Food": {
        "brands": [
            "Maggi","Yippee","Top Ramen","Wai Wai","Patanjali",
            "Knorr","Bambino","Chings Secret","Smith Jones","Nissin",
        ],
        "lines": [
            "2 Minute Noodles","Masala Noodles","Chicken Noodles",
            "Veg Atta Noodles","Cup Noodles Spicy","Rice Noodles",
            "Hakka Noodles","Soupy Noodles","Korean Spicy Noodles",
            "Millet Noodles","Tricolor Pasta","Macaroni Elbow",
            "Vermicelli Roasted","Upma Mix Rava","Poha Mix Instant",
            "Dosa Mix Instant","Idli Mix Instant","Khichdi Instant",
            "Curry Noodles","Peri Peri Noodles",
        ],
        "sizes": [
            ("70g Pack",  12.0, 1.0),
            ("140g Pack", 24.0, 2.0),
            ("300g Pack", 50.0, 4.5),
        ],
        "base_prices": (12, 55),
        "unit": "Pack",
        "target": 200,
        "fast_mover_keywords": ["maggi","yippee","top ramen","wai wai"],
    },
    "Staples": {
        "brands": [
            "Aashirvaad","Fortune","Tata Salt","Patanjali","Annapurna",
            "Saffola","Dhara","Nature Fresh","Rajdhani","India Gate",
            "Kohinoor","Daawat","Catch Spices","MDH Masala","Everest Masala",
            "Tata Tea","Red Label","Wagh Bakri","Bru Coffee","Nescafe",
            "Horlicks","Bournvita","Complan","Glucon D","Boost Energy",
            "Sunrise Coffee","Taj Mahal Tea","Tetley Tea","Green Label",
        ],
        "lines": [
            "Wheat Flour Atta","Multigrain Atta","Super Atta Premium",
            "Maida Refined Flour","Besan Gram Flour","Semolina Rava",
            "Basmati Rice Long","Non Basmati Rice","Brown Rice",
            "Toor Dal Yellow","Moong Dal Green","Chana Dal Yellow",
            "Masoor Dal Red","Rajma Red Kidney","Kabuli Chana White",
            "Thick Poha Flattened","Puffed Rice Murmura",
            "Sunflower Oil Refined","Mustard Oil Kachi Ghani",
            "Groundnut Oil Pure","Coconut Oil Virgin","Soyabean Oil",
            "Rice Bran Oil","Blended Oil",
            "Iodized Salt Fine","Rock Salt Sendha","Black Salt Kala Namak",
            "Sugar Fine White","Jaggery Powder","Pure Honey",
            "Turmeric Powder Haldi","Red Chilli Powder","Coriander Powder",
            "Garam Masala Blend","Cumin Seed Jeera","Black Pepper Whole",
            "Green Cardamom","Cloves Laung","Cinnamon Dalchini",
            "Tea Dust Premium","Tea Leaf CTC","Green Tea Bags",
            "Instant Coffee Powder","Malt Drink Mix","Energy Drink Powder",
        ],
        "sizes": [
            ("500g Pack",  60.0,  1.0),
            ("1kg Pack",  120.0,  2.0),
            ("2kg Pack",  220.0,  4.0),
            ("5kg Pack",  500.0, 10.0),
        ],
        "base_prices": (25, 300),
        "unit": "kg",
        "target": 650,
        "fast_mover_keywords": ["aashirvaad","fortune","tata salt","india gate","daawat","bru","nescafe","tata tea"],
    },
    "Personal Care": {
        "brands": [
            "Lux","Dove","Lifebuoy","Pears","Santoor","Hamam","Cinthol",
            "Dettol","Savlon","Colgate","Pepsodent","Sensodyne","Close Up",
            "Dabur Red","Pantene","Head Shoulders","Sunsilk","Clinic Plus",
            "Tresemme","Garnier","Loreal","Vaseline","Nivea","Parachute",
            "Bajaj Almond","Himalaya Herbals","Emami","Ponds","Gillette",
            "Veet","Anne French",
        ],
        "lines": [
            "Rose Moisturising Soap","Antibacterial Soap","Glycerine Soap",
            "Turmeric Glow Soap","Neem Purifying Soap","Charcoal Soap",
            "Strong Teeth Toothpaste","Fresh Gel Toothpaste","Whitening Toothpaste",
            "Sensitivity Relief Toothpaste","Kids Toothpaste",
            "Soft Bristle Toothbrush","Medium Toothbrush","Tongue Cleaner",
            "Damage Repair Shampoo","Anti Dandruff Shampoo","Smooth Silk Shampoo",
            "Long Strong Shampoo","Keratin Shampoo","Conditioner Daily",
            "Hair Oil Coconut","Hair Serum","Argan Oil Treatment",
            "Daily Moisturiser Lotion","SPF Sunscreen","Night Cream",
            "Face Wash Neem","Face Wash Charcoal","Pimple Clear Face Wash",
            "Talcum Powder Fresh","Deodorant Roll On","Deodorant Spray",
        ],
        "sizes": [
            ("50g",   35.0, 0.5),
            ("100g",  55.0, 1.0),
            ("200ml", 90.0, 2.0),
            ("500ml",180.0, 5.0),
        ],
        "base_prices": (35, 200),
        "unit": "Pack",
        "target": 550,
        "fast_mover_keywords": ["lux","dove","dettol","colgate","pepsodent","pantene","parachute","nivea"],
    },
    "Cleaning": {
        "brands": [
            "Surf Excel","Ariel","Rin","Ghadi","Tide","Nirma","Wheel",
            "Comfort","Vim","Pril","Lizol","Colin","Harpic","Domex",
            "Odonil","Mortein","Good Knight","All Out","Hit","Baygon",
        ],
        "lines": [
            "Washing Powder Regular","Washing Powder Quick Wash","Matic Liquid Detergent",
            "Washing Bar Hard","Fabric Conditioner Jasmine","Fabric Conditioner Rose",
            "Dishwash Bar Lemon","Dishwash Gel Lemon","Dishwash Powder",
            "Floor Cleaner Pine","Floor Cleaner Citrus","Toilet Cleaner Blue",
            "Toilet Cleaner Thick","Glass Cleaner Spray","Bathroom Cleaner",
            "Kitchen Degreaser","Mosquito Coil Green","Mosquito Liquid Refill",
            "Mosquito Spray Instant","Cockroach Spray",
        ],
        "sizes": [
            ("200g Pack",   28.0, 0.5),
            ("500g Pack",   65.0, 1.0),
            ("1kg Pack",   120.0, 2.0),
            ("1L Bottle",   80.0, 2.0),
        ],
        "base_prices": (25, 200),
        "unit": "Pack",
        "target": 350,
        "fast_mover_keywords": ["surf excel","ariel","vim","lizol","harpic","mortein","good knight"],
    },
    "Confectionery": {
        "brands": [
            "Cadbury","Nestle","5 Star","Munch","Perk","Eclairs Candy",
            "Alpenliebe","Center Fresh","Mentos","Polo Mint","Orbit",
            "Boomer Gum","Happydent","Pulse Candy","Kinder Joy",
        ],
        "lines": [
            "Dairy Milk Regular","Fruit Nut Chocolate","Silk Premium",
            "Crispello Wafer","Dark Chocolate","White Chocolate",
            "Toffee Caramel","Mixed Fruit Candy","Mint Polo","Gum Fresh Mint",
            "Gum Strawberry","Lollipop Mango","Hard Candy Assorted",
            "Wafer Chocolate","Praline Mixed",
        ],
        "sizes": [
            ("Single Piece",  5.0, 1.0),
            ("10 Piece Pack", 50.0, 10.0),
            ("50g Bar",       40.0, 0.5),
        ],
        "base_prices": (2, 150),
        "unit": "Pack",
        "target": 200,
        "fast_mover_keywords": ["cadbury","5 star","munch","perk","eclairs"],
    },
    "Tobacco": {
        "brands": [
            "Classic Cigarettes","Gold Flake","Navy Cut","Four Square",
            "Bristol Smokes","Red White","Wills Filter","Benson Hedges",
            "Rajnigandha","Pan Bahar","Vimal Pan Masala","Manikchand",
        ],
        "lines": [
            "Filter King Size","Filter Regular","Filter Lights","Menthol Filter",
            "Slim Cigarettes","Non Filter Bidi",
            "Pan Masala Silver","Pan Masala Gold","Zarda Tobacco",
        ],
        "sizes": [
            ("10 Stick Pack",  50.0, 1.0),
            ("20 Stick Pack",  95.0, 1.0),
            ("Pouch 50g",      80.0, 1.0),
        ],
        "base_prices": (15, 100),
        "unit": "Pack",
        "target": 100,
        "fast_mover_keywords": ["gold flake","classic","navy cut","rajnigandha"],
    },
    "Baby Care": {
        "brands": [
            "Johnsons Baby","Himalaya Baby","Dabur Baby","Huggies",
            "Pampers","Mamy Poko","Mamaearth Baby","Cetaphil Baby",
        ],
        "lines": [
            "Baby Shampoo Gentle","Baby Soap Mild","Baby Lotion Soft",
            "Baby Oil Massage","Baby Powder Talc","Baby Wipes Wet",
            "Diaper Pants S Size","Diaper Pants M Size",
            "Diaper Pants L Size","Diaper Pants XL Size",
            "Rash Cream Protective","Baby Wash 2in1",
            "Baby Cereal Rice Stage1","Baby Cereal Wheat Stage2",
        ],
        "sizes": [
            ("100g",           90.0,  1.0),
            ("200ml",         130.0,  1.0),
            ("Pack of 20 Diapers", 220.0, 1.0),
        ],
        "base_prices": (80, 300),
        "unit": "Pack",
        "target": 100,
        "fast_mover_keywords": ["johnsons","huggies","pampers","mamy poko"],
    },
    "Frozen": {
        "brands": [
            "McCain","Godrej Yummiez","Suguna","Venkys",
            "Kwality Walls","Amul Frozen","Vadilal","Oven Story",
        ],
        "lines": [
            "Potato Wedges Crispy","French Fries Classic","Corn Nuggets",
            "Veg Burger Patty","Chicken Nuggets","Chicken Strips",
            "Spring Roll Veg","Spring Roll Chicken","Pizza Base",
            "Ice Cream Vanilla","Ice Cream Chocolate","Kulfi Mango",
            "Frozen Green Peas","Frozen Sweet Corn","Frozen Mixed Veg",
        ],
        "sizes": [
            ("250g Pack", 100.0, 1.0),
            ("500g Pack", 190.0, 2.0),
        ],
        "base_prices": (80, 250),
        "unit": "Pack",
        "target": 110,
        "fast_mover_keywords": ["mccain","kwality walls","amul frozen","vadilal"],
    },
    "Health OTC": {
        "brands": [
            "Revital","Dabur","Zandu","Amrutanjan","Iodex","Moov",
            "Volini","Digene","Eno","Hajmola","Patanjali Health","Electral",
        ],
        "lines": [
            "Multivitamin Daily","Calcium Plus Vitamin D","Iron Folic Acid",
            "Vitamin C Effervescent","Chyawanprash Original","Chyawanprash Special",
            "Digestive Tablets","Antacid Gel","Pain Relief Ointment Strong",
            "Cold Balm Original","Muscle Relief Spray","Glucose Powder Orange",
            "Glucose Powder Lemon","ORS Oral Rehydration","Immunity Booster",
        ],
        "sizes": [
            ("50g",        60.0, 1.0),
            ("100g",      100.0, 1.0),
            ("30 Tablets", 90.0, 1.0),
        ],
        "base_prices": (50, 350),
        "unit": "Pack",
        "target": 160,
        "fast_mover_keywords": ["eno","digene","hajmola","moov","volini","zandu balm"],
    },
    "Stationery": {
        "brands": [
            "Natraj","Classmate","Apsara","Camlin","Faber Castell",
            "Navneet","Rorito",
        ],
        "lines": [
            "Ball Pen Blue Ink","Ball Pen Black Ink","Ball Pen Red Ink",
            "Gel Pen Smooth","Pencil HB Grade","Pencil 2B Grade",
            "Eraser Soft White","Pencil Sharpener","30cm Ruler Scale",
            "Notebook 100 Pages Ruled","Notebook 200 Pages Ruled",
            "Drawing Book A4","Crayon Set 12 Colours","Sketch Pen Set 24",
            "Highlighter Yellow",
        ],
        "sizes": [
            ("Single Piece",  8.0, 1.0),
            ("Pack of 10",   70.0, 1.0),
        ],
        "base_prices": (5, 100),
        "unit": "Piece",
        "target": 90,
        "fast_mover_keywords": ["natraj","apsara","classmate"],
    },
    "Pet Food": {
        "brands": [
            "Pedigree","Drools","Royal Canin","Whiskas",
            "Me-O","Chappi","Purina",
        ],
        "lines": [
            "Adult Dog Chicken Rice","Adult Dog Vegetarian","Puppy Food Chicken",
            "Senior Dog Chicken","Dog Treat Biscuit Milk","Dog Treat Chicken Strip",
            "Adult Cat Fish Ocean","Adult Cat Chicken","Kitten Growth Formula",
            "Cat Treat Temptations","Fish Food Tropical",
        ],
        "sizes": [
            ("500g Pack",  200.0, 1.0),
            ("1.2kg Pack", 450.0, 1.0),
        ],
        "base_prices": (150, 600),
        "unit": "Pack",
        "target": 75,
        "fast_mover_keywords": ["pedigree","drools","whiskas"],
    },
}

# Fix Health OTC price_range typo guard
CATALOG["Health OTC"]["base_prices"] = (50, 350)

# ═══════════════════════════════════════════════════════════════════════════
#  INDIAN NAME BANKS  — 250 first names × 200 last names = 50,000 combos
# ═══════════════════════════════════════════════════════════════════════════
FIRST_NAMES = [
    # Male (125)
    "Aarav","Aditya","Ajay","Akash","Amit","Anand","Anil","Ankur","Anuj","Arjun",
    "Arpit","Ashish","Ashok","Atul","Avinash","Bharat","Deepak","Dhruv","Dilip",
    "Dinesh","Gaurav","Girish","Gopal","Harish","Hemant","Hitesh","Jagdish","Jatin",
    "Karan","Kartik","Kaushik","Lalit","Manoj","Manish","Milind","Mohit","Mukesh",
    "Naresh","Naveen","Nikhil","Nitin","Pankaj","Parth","Piyush","Pradeep","Prakash",
    "Prasad","Praveen","Puneet","Rahul","Rajesh","Rajiv","Rajan","Rakesh","Ram",
    "Ramesh","Ravi","Ritesh","Rohan","Rohit","Sachin","Sagar","Sanjay","Sanjeev",
    "Santosh","Satish","Shyam","Siddharth","Sunil","Suresh","Tanmay","Tarun","Uday",
    "Umesh","Varun","Vijay","Vikram","Vinay","Vinod","Vishal","Vivek","Yash","Yogesh",
    "Abhishek","Advait","Agastya","Akshay","Aniket","Ankit","Aryan","Chirag","Dev",
    "Eshan","Farhan","Harsh","Ishan","Jay","Kabir","Lakshya","Mayur","Neeraj","Omkar",
    "Pranav","Raghav","Rishabh","Sameer","Saurabh","Shubham","Subhash","Sumit","Suraj",
    "Swapnil","Tej","Umang","Vedant","Vikas","Yuvraj","Zahir","Chetan","Devang","Fenil",
    "Gaurang","Hardik","Jignesh","Kushal","Maulik","Nirav","Parimal","Ruchit","Shreyans",
    "Tejas","Viral","Alpesh","Bhavesh","Darshan","Giriraj","Haresh","Kamlesh",
    # Female (125)
    "Aarti","Aditi","Alka","Amita","Amruta","Anita","Anjali","Ankita","Anupama",
    "Asha","Ayesha","Babita","Bhavna","Chhaya","Deepa","Deepika","Divya","Durga",
    "Fatima","Gauri","Geeta","Hema","Isha","Jaya","Jyoti","Kajal","Kamala","Kavita",
    "Kiran","Komal","Kumari","Lakshmi","Lata","Madhuri","Mamta","Manisha","Maya",
    "Meena","Meenakshi","Meera","Monika","Namrata","Nandita","Neelam","Neeta","Neha",
    "Nisha","Nita","Padma","Payal","Poonam","Pooja","Pragya","Priti","Priya","Rachna",
    "Radha","Rajni","Rekha","Reshma","Ritu","Rupa","Sapna","Sarita","Savita","Seema",
    "Shanti","Shraddha","Shreya","Sneha","Sonal","Sonia","Sudha","Sunita","Supriya",
    "Swati","Tara","Usha","Vandana","Varsha","Vidya","Vimla","Vinita","Yamini","Zara",
    "Zoya","Akansha","Amisha","Ananya","Bhumi","Charvi","Diksha","Ekta","Garima",
    "Harshita","Ishita","Juhi","Khushi","Lavanya","Mansi","Nidhi","Pallavi","Pari",
    "Prachi","Ridhi","Riya","Sakshi","Shivangi","Simran","Smriti","Tanvi","Trupti",
    "Urvi","Vaishnavi","Yashvi","Chetna","Drashti","Foram","Gopi","Heena","Jagruti",
    "Kinjal","Mittal","Nirali","Poonam","Riddhi","Smita","Tejal","Varna","Zinnia",
]

LAST_NAMES = [
    "Agarwal","Ahuja","Ansari","Arora","Bajaj","Banerjee","Bansal","Batra","Bhatt",
    "Bose","Chauhan","Chawla","Choudhari","Choudhury","Datta","Dave","Desai",
    "Deshpande","Dubey","Dutta","Gandhi","Garg","Ghosh","Goswami","Goyal","Gupta",
    "Iyer","Jain","Jaiswal","Jha","Joshi","Kapur","Kapoor","Kaur","Khanna","Kohli",
    "Kumar","Lal","Malhotra","Mehrotra","Mehta","Mishra","Modi","Mohan","Mukherjee",
    "Nair","Nath","Pandey","Patel","Pathak","Patil","Paul","Pillai","Prasad",
    "Rajput","Rao","Rastogi","Rawat","Reddy","Roy","Sahoo","Sahu","Saxena","Shah",
    "Sharma","Shukla","Singh","Sinha","Soni","Srivastava","Thakur","Tiwari",
    "Tripathi","Varma","Verma","Yadav","Ahir","Bahl","Baid","Bajpai","Bhardwaj",
    "Bhatia","Bhattacharya","Bisht","Chakraborty","Chandra","Chatterjee","Chouhan",
    "Das","Deol","Dhawan","Dhingra","Dixit","Dube","Duggal","Goel","Grover","Guha",
    "Gulati","Gumber","Handa","Hora","Jagtap","Jolly","Kadam","Kamble","Kashyap",
    "Katiyar","Khare","Kulkarni","Londhe","Luthra","Madan","Mane","Marwah","Mathur",
    "Mehra","Menon","Mhatre","Nagpal","Naik","Narula","Nijhawan","Oberoi","Parekh",
    "Parikh","Pasricha","Puri","Raina","Rajpal","Saraf","Sathe","Sawhney","Sawant",
    "Sethi","Shekhawat","Shinde","Subramaniam","Sukhija","Suri","Talwar","Taneja",
    "Tandon","Thapar","Tyagi","Upadhyay","Vaidya","Vaid","Virmani","Walia","Zaveri",
    "Narayanan","Krishnan","Balaji","Swaminathan","Venkatesh","Ramachandran",
    "Balachandran","Raghavan","Sundaram","Natarajan","Subrahmanian","Parthasarathy",
    "Seetharaman","Annamalai","Murugan","Rajendran","Palaniswamy","Venkataramaiah",
    "Lakshminarayana","Rajagopalan","Seshadri","Thyagarajan","Chakravarthy",
    "Satyanarayana","Hanumantha","Veeraiah","Srinivasa","Nagabhushanam",
    "Datta","Lahiri","Biswas","Chowdhury","Bhowmik","Sarkar","Mondal","Adhikari",
    "Bhaumik","Bandyopadhyay","Mukhopadhyay","Haldar","Mandal","Saha","Basu",
]

CITY_AREAS = [
    # Delhi NCR
    "Rohini Sector 4 Delhi","Lajpat Nagar Delhi","Okhla Phase 2 Delhi",
    "Dwarka Sector 11 Delhi","Pitampura Delhi","Janakpuri Delhi",
    "Mayur Vihar Phase 1 Delhi","Vasant Kunj Delhi","Saket Delhi",
    "Nehru Place Delhi","Laxmi Nagar Delhi","Shahdara Delhi",
    "Paschim Vihar Delhi","Tilak Nagar Delhi","Rajouri Garden Delhi",
    "Uttam Nagar Delhi","Kalkaji Delhi","Greater Kailash Delhi",
    "Jamia Nagar Delhi","Malviya Nagar Delhi","Karol Bagh Delhi",
    "Chandni Chowk Delhi","Model Town Delhi","Wazirpur Delhi",
    "Rohtak Road Delhi","Nangloi Delhi","Palam Delhi",
    "Vasant Vihar Delhi","R K Puram Delhi","Hauz Khas Delhi",
    "South Extension Delhi","Jangpura Delhi","Nizamuddin Delhi",
    "Ashok Vihar Delhi","Shalimar Bagh Delhi","Vikaspuri Delhi",
    "Sector 18 Noida","Sector 62 Noida","Sector 63 Noida",
    "Vaishali Ghaziabad","Indirapuram Ghaziabad","Sector 21 Faridabad",
    "DLF Phase 1 Gurgaon","Sector 56 Gurgaon","Sohna Road Gurgaon",
    # Mumbai
    "Andheri East Mumbai","Andheri West Mumbai","Bandra West Mumbai",
    "Borivali West Mumbai","Kandivali West Mumbai","Malad West Mumbai",
    "Goregaon East Mumbai","Thane West Mumbai","Mulund West Mumbai",
    "Ghatkopar West Mumbai","Chembur Mumbai","Kurla West Mumbai",
    "Dadar West Mumbai","Worli Mumbai","Lower Parel Mumbai",
    "Byculla Mumbai","Grant Road Mumbai","Colaba Mumbai",
    "Navi Mumbai Vashi","Navi Mumbai Kharghar","Mira Road Mumbai",
    # Bengaluru
    "Koramangala Bengaluru","Indiranagar Bengaluru","HSR Layout Bengaluru",
    "BTM Layout Bengaluru","Jayanagar Bengaluru","Marathahalli Bengaluru",
    "Whitefield Bengaluru","Electronic City Bengaluru","Bannerghatta Road Bengaluru",
    "Hebbal Bengaluru","Yelahanka Bengaluru","Rajajinagar Bengaluru",
    "Malleswaram Bengaluru","Basavanagudi Bengaluru","JP Nagar Bengaluru",
    # Hyderabad
    "Banjara Hills Hyderabad","Jubilee Hills Hyderabad","Madhapur Hyderabad",
    "Gachibowli Hitech City","Kondapur Hyderabad","Kukatpally Hyderabad",
    "Ameerpet Hyderabad","Secunderabad","Dilsukhnagar Hyderabad",
    "Miyapur Hyderabad","LB Nagar Hyderabad","Uppal Hyderabad",
    # Pune
    "Kothrud Pune","Karve Nagar Pune","Aundh Pune","Baner Pune",
    "Wakad Pune","Hinjewadi Pune","Pimple Saudagar Pune",
    "Hadapsar Pune","Magarpatta Pune","Viman Nagar Pune",
    "Koregaon Park Pune","Shivajinagar Pune","Deccan Pune",
    # Chennai
    "Anna Nagar Chennai","T Nagar Chennai","Adyar Chennai",
    "Velachery Chennai","Tambaram Chennai","Guindy Chennai",
    "Nungambakkam Chennai","Alwarpet Chennai","Mylapore Chennai",
    "Sholinganallur Chennai","Perungudi OMR Chennai","Porur Chennai",
    "Ambattur Chennai","Avadi Chennai",
    # Other cities
    "Salt Lake City Kolkata","New Town Kolkata","Park Street Kolkata",
    "Satellite Ahmedabad","Navrangpura Ahmedabad","Adajan Surat",
    "Alkapuri Vadodara","Vaishali Nagar Jaipur","Mansarovar Jaipur",
    "Hazratganj Lucknow","Gomti Nagar Lucknow","Civil Lines Kanpur",
    "Boring Road Patna","Kankarbagh Patna","Vijay Nagar Indore",
    "Dharampeth Nagpur","New Market Bhopal","Sector 17 Chandigarh",
    "Phase 7 Mohali","Kakkanad Kochi","MG Road Kochi",
    "Pattom Trivandrum","RS Puram Coimbatore","Anna Nagar Madurai",
    "MVP Colony Visakhapatnam","Steel Plant Area Visakhapatnam",
    "Durgapur WB","Asansol WB","Bokaro Steel City",
    "Raipur CG","Bhopal MP","Gwalior MP","Jabalpur MP",
    "Bhilai CG","Korba CG","Bilaspur CG",
    "Dehradun Uttarakhand","Haridwar Uttarakhand","Rishikesh Uttarakhand",
    "Shimla Himachal","Manali Himachal","Dharamshala Himachal",
    "Amritsar Punjab","Ludhiana Punjab","Patiala Punjab","Jalandhar Punjab",
    "Jodhpur Rajasthan","Udaipur Rajasthan","Ajmer Rajasthan","Kota Rajasthan",
    "Agra UP","Varanasi UP","Allahabad UP","Meerut UP","Bareilly UP",
    "Nashik Maharashtra","Aurangabad Maharashtra","Kolhapur Maharashtra","Solapur Maharashtra",
]

# ═══════════════════════════════════════════════════════════════════════════
#  SUPPLIER NAME BANKS
# ═══════════════════════════════════════════════════════════════════════════
SUPPLIER_KEYWORDS = [
    # FMCG brands
    "PepsiCo","Frito-Lay","Haldiram","ITC Snacks","Balaji Wafers","Bikaji Foods",
    "Parle Agro","Bikanervala","Prataap Snacks","Catch Foods","Too Yumm",
    "Hindustan Coca-Cola","Varun Beverages","RC Cola","Parle Agro Drinks",
    "Dabur Beverages","Manpasand","Paper Boat Hector","Amul India","Mother Dairy",
    "Nestle India","Danone India","Heritage Foods","Parag Milk","Prabhat Dairy",
    "Godrej Agrovet","ITC Yippee","Wai Wai","Chings Secret","Knorr India",
    "Britannia Industries","Parle Products","Sunfeast ITC","Anmol Biscuits",
    "Priyagold Foods","Bonn Nutrients","Tata Consumer","Aashirvaad ITC",
    "Fortune Adani","Saffola Marico","Dhara NDDB","Ruchi Soya","Gemini Edibles",
    "Emami Agrotech","Kohinoor Foods","India Gate KRBL","Daawat LT Foods",
    "Charminar Rice","Tirumala Milk","Vijaya Dairy","Nandini Milk","Aavin Tamil Nadu",
    "Milma Kerala","Saras Rajasthan","HUL India","Procter Gamble India",
    "Reckitt India","Colgate Palmolive","Dabur India","Emami Limited",
    "Himalaya Drug","Marico Industries","Godrej Consumer","Bajaj Consumer",
    "CavinKare","VLCC India","Jyothy Labs","Wipro Consumer","Nirma Limited",
    "Henkel India","SC Johnson India","Godrej Household","Fena Detergent",
    "Ghadi Rohit Surfactants","ITC Cigarettes","Godfrey Phillips","VST Industries",
    "GPI Tobacco","Manikchand","Dharampal Satyapal","Pan Parag","Kothari Products",
    "Mondelez India","Mars India","Nestle Confectionery","Perfetti Van Melle",
    "Candico India","Lotte India","Nutrine Confectionery","Ravalgaon",
    # Distribution/logistics type names
    "Agro Fresh","AgroMart","Apex Distribution","Balram Traders","Bengal Agro",
    "Bharati Enterprises","Bhavna Distributors","Champa Trading","Choice Agencies",
    "City Fresh Supply","Classic Traders","Continental Foods","Crown Agencies",
    "Devi Marketing","Diamond Supply","Eastern Traders","Elite Distribution",
    "Empire Wholesale","Excel Trading","Federal Agencies","Fine Goods",
    "First Choice Supply","Fortune Traders","Galaxy Distribution","Ganesh Agencies",
    "Global Mart","Goodluck Traders","Grand Wholesale","Green Valley Foods",
    "Gupta Brothers Trading","Hanuman Enterprises","Happy Traders","Hari Om Supply",
    "Harish Distribution","Heritage Agro","Hills Foods","Hindustan Supply",
    "Hira Trading","Horizon Agencies","Ideal Distributors","Imperial Supply",
    "India Fresh","Indian Agro","Indus Traders","Jagdamba Supply","Jai Hind Agencies",
    "Jai Mata Di Traders","Jana Wholesale","Jasmine Enterprises","Jay Ambe Supply",
    "Joshi Brothers","JSK Agencies","Kamal Enterprises","Kapil Traders",
    "Kaveri Agro","Kesari Supply","Kiran Trading","Kohinoor Supply",
    "Krishna Agencies","Kumar Brothers","Laxmi Enterprises","Lotus Traders",
    "Lucky Agencies","Mahalaxmi Supply","Mahesh Traders","Mahindra Agro",
    "Maruti Enterprises","Metro Distribution","Milan Traders","Modern Agencies",
    "Mohit Trading","Murugan Supply","National Foods","Nav Durga Trading",
    "Navkar Agencies","Navratna Enterprises","New Age Supply","New India Traders",
    "Nihal Agencies","Nilgiri Fresh","Noble Distributors","Northern Supply",
    "Om Sai Agencies","Om Shanti Traders","Oriental Foods","Padmavati Enterprises",
    "Pal Traders","Paramount Supply","Patel Brothers","Patil Agencies",
    "Pioneer Distribution","Pooja Enterprises","Pragati Traders","Prasad Supply",
    "Premium Agencies","Prime Distributors","Prince Trading","Priya Enterprises",
    "Punjab Fresh","Rajdhani Supply","Rajesh Agencies","Rajput Traders",
    "Ram Janaki Enterprises","Rama Supply","Ramesh Brothers","Rashmi Trading",
    "Reliance Agro","Renu Enterprises","Rishabh Agencies","Rohini Fresh",
    "Royal Traders","Sai Krupa Supply","Sainath Agencies","Samarth Distribution",
    "Sanjay Traders","Sanmati Supply","Santosh Enterprises","Saraswati Agro",
    "Sarkar Brothers","Sarv Mangal Supply","Sarvottam Trading","Satya Sai Agencies",
    "Savitri Enterprises","Shanti Agencies","Sharma Brothers","Shilpa Traders",
    "Shiv Shakti Supply","Shivam Distribution","Shreejee Agencies","Shreenath Supply",
    "Siddhi Vinayak","Singh Brothers","Srinivas Supply","Star Agencies",
    "Subhash Trading","Sudarshan Supply","Sukh Sagar Traders","Sunder Agencies",
    "Suresh Brothers","Swastik Supply","Tapadia Enterprises","Tara Agencies",
    "Tirupati Supply","Today Traders","Trimurti Distribution","Triveni Agencies",
    "Uma Shankar Traders","United Supply","Usha Enterprises","Uttam Agencies",
    "Vaibhav Trading","Vardhan Supply","Varsha Enterprises","Vasudha Agro",
    "Vijay Agencies","Vikram Traders","Vinayak Supply","Vinod Brothers",
    "Vishnu Enterprises","Western Traders","Yadav Brothers","Yogesh Agencies",
    "Zonal Supply","Zones Distribution",
]

SUPPLIER_SUFFIXES = [
    "Distributors","Traders","Agencies","Pvt Ltd","Enterprises",
    "Distribution Hub","Wholesale Depot","& Co","Trading Company","Suppliers",
]

# ═══════════════════════════════════════════════════════════════════════════
#  SUPPLIER → CATEGORY MAPPING  (keyword-based)
# ═══════════════════════════════════════════════════════════════════════════
SUPPLIER_CAT_KEYWORDS = {
    "Snacks":         ["frito","haldiram","bikaji","balaji","prataap","too yumm","bikanervala"],
    "Beverages":      ["coca-cola","pepsico","varun","parle agro","dabur bev","manpasand","paper boat","hector","b natural"],
    "Dairy":          ["amul","mother dairy","nestle","parag","verka","gowardhan","heritage foods","milma","aavin","nandini","vijaya","dodla","prabhat","saras","tirumala"],
    "Bakery":         ["britannia","parle products","sunfeast","anmol","priyagold","bonn"],
    "Instant Food":   ["yippee","wai wai","chings","knorr","bambino","maggi","nestle food"],
    "Staples":        ["aashirvaad","fortune adani","saffola","dhara","ruchi soya","gemini","emami agro","kohinoor","india gate","daawat","charminar"],
    "Personal Care":  ["hul","procter","reckitt","colgate","dabur india","emami limited","himalaya","marico","godrej consumer","bajaj consumer","cavin","vlcc","jyothy","wipro"],
    "Cleaning":       ["nirma","henkel","sc johnson","godrej household","fena","ghadi"],
    "Confectionery":  ["mondelez","mars","perfetti","candico","lotte","nutrine","ravalgaon"],
    "Tobacco":        ["itc cig","godfrey","vst","gpi","manikchand","dharampal","pan parag","kothari"],
}

# ═══════════════════════════════════════════════════════════════════════════
#  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def get_connection():
    os.makedirs(BASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-128000;")
    conn.execute("PRAGMA foreign_keys=OFF;")   # OFF during bulk seed
    return conn


def create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT
        );
        CREATE TABLE IF NOT EXISTS product_variant (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            unit TEXT DEFAULT 'Unit',
            current_stock REAL DEFAULT 0,
            FOREIGN KEY(product_id) REFERENCES product(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            mobile TEXT,
            address TEXT,
            balance REAL DEFAULT 0,
            next_payment_date TEXT
        );
        CREATE TABLE IF NOT EXISTS credit_sale (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            sale_date TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS credit_sale_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            price_at_sale REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES credit_sale(id) ON DELETE CASCADE,
            FOREIGN KEY(variant_id) REFERENCES product_variant(id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS payment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            payment_date TEXT DEFAULT (datetime('now','localtime')),
            amount REAL NOT NULL,
            payment_mode TEXT NOT NULL DEFAULT 'Cash',
            FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS supplier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            mobile TEXT,
            address TEXT,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS purchase_invoice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            invoice_date TEXT DEFAULT (datetime('now','localtime')),
            total_amount REAL NOT NULL,
            reference_number TEXT,
            FOREIGN KEY(supplier_id) REFERENCES supplier(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS purchase_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES purchase_invoice(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        );

        CREATE TABLE IF NOT EXISTS model_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT UNIQUE NOT NULL,
            task_type TEXT NOT NULL CHECK(task_type IN ('churn', 'forecast', 'market_basket')),
            algorithm TEXT NOT NULL,
            model_version TEXT NOT NULL,
            trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trained_rows INTEGER NOT NULL,
            data_window_months INTEGER DEFAULT 24,
            feature_version TEXT DEFAULT 'v1',
            file_path TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            is_active INTEGER DEFAULT 0 CHECK(is_active IN (0,1)),
            promoted_at TIMESTAMP,
            replaced_by TEXT,
            evaluation_status TEXT CHECK(evaluation_status IN ('pending', 'approved', 'rejected')),
            evaluation_notes TEXT,
            FOREIGN KEY (replaced_by) REFERENCES model_registry(model_id)
        );

        CREATE TABLE IF NOT EXISTS dataset_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            row_count INTEGER NOT NULL,
            feature_version TEXT,
            feature_hash TEXT,
            missing_rate REAL,
            outlier_rate REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (model_id) REFERENCES model_registry(model_id)
        );

        CREATE TABLE IF NOT EXISTS prediction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            task_type TEXT NOT NULL,
            model_version TEXT NOT NULL,
            total_predictions INTEGER,
            avg_prediction REAL,
            high_risk_count INTEGER,
            p25 REAL,
            p50 REAL,
            p75 REAL,
            p95 REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, task_type, model_version) ON CONFLICT REPLACE
        );

        CREATE TABLE IF NOT EXISTS analytics_snapshot (
            model_name TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_model_task_active ON model_registry(task_type, is_active);
        CREATE INDEX IF NOT EXISTS idx_model_trained_at ON model_registry(trained_at DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshot_model ON dataset_snapshots(model_id);
        CREATE INDEX IF NOT EXISTS idx_pred_log_date ON prediction_log(date DESC);
    """)
    conn.commit()


def create_indexes(conn):
    print("   Creating indexes…")
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_credit_sale_customer_date ON credit_sale(customer_id, sale_date DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sale_date ON credit_sale(sale_date);",
        "CREATE INDEX IF NOT EXISTS idx_item_sale ON credit_sale_item(sale_id);",
        "CREATE INDEX IF NOT EXISTS idx_sale_item_variant ON credit_sale_item(variant_id);",
        "CREATE INDEX IF NOT EXISTS idx_payment_customer_date ON payment(customer_id, payment_date DESC);",
        "CREATE INDEX IF NOT EXISTS idx_customer_balance ON customer(balance);",
        "CREATE INDEX IF NOT EXISTS idx_customer_payment_date ON customer(next_payment_date);",
        "CREATE INDEX IF NOT EXISTS idx_customer_name ON customer(name);",
        "CREATE INDEX IF NOT EXISTS idx_customer_mobile ON customer(mobile);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_invoice_date_desc ON purchase_invoice(invoice_date DESC, supplier_id);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_invoice_supplier_date ON purchase_invoice(supplier_id, invoice_date DESC);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_item_invoice ON purchase_item(invoice_id);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_item_variant ON purchase_item(variant_id);",
        "CREATE INDEX IF NOT EXISTS idx_supplier_name ON supplier(name);",
        "CREATE INDEX IF NOT EXISTS idx_supplier_mobile ON supplier(mobile);",
        "CREATE INDEX IF NOT EXISTS idx_supplier_is_deleted ON supplier(is_deleted);",
        "CREATE INDEX IF NOT EXISTS idx_product_name ON product(name);",
        "CREATE INDEX IF NOT EXISTS idx_variant_name ON product_variant(name);",
        "CREATE INDEX IF NOT EXISTS idx_variant_product ON product_variant(product_id);",
    ]:
        conn.execute(sql)
    conn.commit()
    print("   ✅ Indexes created.")


# ═══════════════════════════════════════════════════════════════════════════
#  GENERATE PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════
def generate_products(conn, rng):
    print("\n🛒  Generating products & variants…")
    c = conn.cursor()

    product_rows = []   # (name, category)
    variant_rows = []   # (product_name, variant_name, price, unit, stock, is_fast)

    used_names = set()

    for cat_name, cat in CATALOG.items():
        combos = list(iproduct(cat["brands"], cat["lines"]))
        rng.shuffle(combos)
        target = cat["target"]
        count = 0

        for brand, line in combos:
            if count >= target:
                break
            prod_name = f"{brand} {line}"
            if prod_name in used_names:
                continue
            used_names.add(prod_name)
            product_rows.append((prod_name, cat_name))
            count += 1

            # Variants: base price + larger sizes at price multipliers
            base_min, base_max = cat["base_prices"]
            base_price = float(rng.integers(base_min, base_max + 1))

            sizes = cat["sizes"]
            n_variants = int(rng.integers(1, min(3, len(sizes)) + 1))
            chosen_sizes = sizes[:n_variants]  # smallest N sizes

            is_fast = any(kw in prod_name.lower() for kw in cat.get("fast_mover_keywords", []))
            for s_name, s_price_override, s_multiplier in chosen_sizes:
                # Use catalog base price scaled by size multiplier
                price = round(base_price * s_multiplier + float(rng.integers(0, 10)), 2)
                price = max(float(cat["base_prices"][0]), price)
                # Opening stock: fast-movers low (trigger stockout alerts), rest normal
                stock = float(rng.integers(5, 20) if is_fast else rng.integers(20, 80))
                variant_rows.append((prod_name, s_name, price, cat["unit"], stock))

    print(f"   {len(product_rows)} products, {len(variant_rows)} variants to insert…")

    # Bulk insert products
    c.executemany("INSERT OR IGNORE INTO product (name, category) VALUES (?, ?)", product_rows)
    conn.commit()

    # Fetch product_id map
    c.execute("SELECT id, name FROM product")
    pid_map = {row[1]: row[0] for row in c.fetchall()}

    # Bulk insert variants
    variant_db_rows = [
        (pid_map[pname], vname, price, unit, stock)
        for pname, vname, price, unit, stock in variant_rows
        if pname in pid_map
    ]
    c.executemany(
        "INSERT INTO product_variant (product_id, name, price, unit, current_stock) VALUES (?,?,?,?,?)",
        variant_db_rows
    )
    conn.commit()

    total_p = c.execute("SELECT COUNT(*) FROM product").fetchone()[0]
    total_v = c.execute("SELECT COUNT(*) FROM product_variant").fetchone()[0]
    print(f"   ✅ {total_p} products, {total_v} variants inserted.")
    return pid_map


# ═══════════════════════════════════════════════════════════════════════════
#  GENERATE CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════
def generate_customers(conn, rng):
    print(f"\n👥  Generating {TARGET_CUSTOMERS} customers…")
    c = conn.cursor()

    # Build all first×last combos, shuffle, pick unique 10000
    first_arr = np.array(FIRST_NAMES)
    last_arr  = np.array(LAST_NAMES)
    rng.shuffle(first_arr)
    rng.shuffle(last_arr)

    names = []
    used = set()
    attempt = 0
    while len(names) < TARGET_CUSTOMERS:
        fi = rng.integers(0, len(FIRST_NAMES))
        li = rng.integers(0, len(LAST_NAMES))
        name = f"{FIRST_NAMES[fi]} {LAST_NAMES[li]}"
        if name not in used:
            used.add(name)
            names.append(name)
        attempt += 1
        if attempt > TARGET_CUSTOMERS * 20:
            # Append suffix to force uniqueness
            name = f"{name} {rng.integers(10,99)}"
            if name not in used:
                used.add(name)
                names.append(name)

    def gen_mobile(rng):
        prefix = rng.choice([70,72,73,74,75,76,77,78,79,
                              80,81,82,83,84,85,86,87,88,89,
                              90,91,92,93,94,95,96,97,98,99])
        return f"{prefix}{rng.integers(10000000, 99999999):08d}"

    customer_rows = []
    for name in names:
        mobile  = gen_mobile(rng)
        address = str(rng.choice(CITY_AREAS))
        customer_rows.append((name, mobile, address))

    c.executemany(
        "INSERT OR IGNORE INTO customer (name, mobile, address) VALUES (?,?,?)",
        customer_rows
    )
    conn.commit()

    c.execute("SELECT id, name FROM customer ORDER BY id")
    rows = c.fetchall()
    print(f"   ✅ {len(rows)} customers inserted.")
    return rows


# ═══════════════════════════════════════════════════════════════════════════
#  GENERATE SUPPLIERS
# ═══════════════════════════════════════════════════════════════════════════
def generate_suppliers(conn, rng):
    print(f"\n🏭  Generating {TARGET_SUPPLIERS} suppliers…")
    c = conn.cursor()

    used_names = set()
    supplier_rows = []
    keywords = list(SUPPLIER_KEYWORDS)
    rng.shuffle(keywords)

    for kw in keywords:
        for suf in SUPPLIER_SUFFIXES:
            if len(supplier_rows) >= TARGET_SUPPLIERS:
                break
            sname = f"{kw} {suf}"
            if sname not in used_names:
                used_names.add(sname)
                mobile = f"9{rng.integers(100000000, 999999999):09d}"
                area   = str(rng.choice(CITY_AREAS))
                supplier_rows.append((sname, mobile, area))
        if len(supplier_rows) >= TARGET_SUPPLIERS:
            break

    c.executemany(
        "INSERT OR IGNORE INTO supplier (name, mobile, address) VALUES (?,?,?)",
        supplier_rows
    )
    conn.commit()

    c.execute("SELECT id, name FROM supplier ORDER BY id")
    rows = c.fetchall()
    print(f"   ✅ {len(rows)} suppliers inserted.")
    return rows


# ═══════════════════════════════════════════════════════════════════════════
#  BUILD & SAVE MAPS
# ═══════════════════════════════════════════════════════════════════════════
def build_and_save_maps(conn, customer_rows, supplier_rows, rng):
    print("\n🗺️   Building seed maps…")
    c = conn.cursor()

    # ── Variants ──────────────────────────────────────────────────────────
    c.execute("""
        SELECT pv.id, pv.price, pv.current_stock, p.name, p.category
        FROM product_variant pv
        JOIN product p ON pv.product_id = p.id
    """)
    vdata = c.fetchall()

    all_variant_ids        = [r[0] for r in vdata]
    variant_price_map      = {str(r[0]): r[1] for r in vdata}
    variant_opening_stock  = {str(r[0]): r[2] for r in vdata}
    variant_to_product     = {str(r[0]): r[3] for r in vdata}
    variant_to_category    = {str(r[0]): r[4] for r in vdata}

    # Reorder point per variant: ~15-20% of opening stock, min 5
    variant_reorder_point = {
        str(r[0]): max(5.0, round(r[2] * 0.18, 1)) for r in vdata
    }

    # product_name → list of variant ids
    product_to_variants = {}
    for vid, _, _, pname, _ in vdata:
        product_to_variants.setdefault(pname, []).append(vid)

    # category → list of variant ids
    cat_to_variants = {}
    for vid, _, _, _, cat in vdata:
        cat_to_variants.setdefault(cat, []).append(vid)

    # ── Suppliers ─────────────────────────────────────────────────────────
    supplier_ids = [r[0] for r in supplier_rows]
    # Map supplier_id → categories it covers (keyword matching)
    supplier_cat_map = {}
    for sid, sname in supplier_rows:
        cats = []
        sname_low = sname.lower()
        for cat, kws in SUPPLIER_CAT_KEYWORDS.items():
            if any(kw in sname_low for kw in kws):
                cats.append(cat)
        if not cats:
            # Generic supplier — assign 2-3 random categories
            all_cats = list(CATALOG.keys())
            n = int(rng.integers(2, 4))
            cats = [str(all_cats[i]) for i in rng.choice(len(all_cats), size=n, replace=False)]
        supplier_cat_map[str(sid)] = cats

    # ── Customers ─────────────────────────────────────────────────────────
    customer_ids = [r[0] for r in customer_rows]
    n_cust = len(customer_ids)

    # Segments: loyal 40%, credit 25%, occasional 25%, at_risk 10%
    seg_labels = (["loyal"] * 40 + ["credit"] * 25 + ["occasional"] * 25 + ["at_risk"] * 10) * (n_cust // 100 + 1)
    seg_labels = seg_labels[:n_cust]
    rng.shuffle(seg_labels)
    customer_segments = {str(customer_ids[i]): seg_labels[i] for i in range(n_cust)}

    # Credit customers = all "credit" + 40% of "loyal"
    credit_customer_ids = []
    for i, cid in enumerate(customer_ids):
        seg = seg_labels[i]
        if seg == "credit":
            credit_customer_ids.append(cid)
        elif seg == "loyal" and rng.random() < 0.12:
            credit_customer_ids.append(cid)
    credit_set = set(credit_customer_ids)

    # Credit limit per customer (log-normal, median ~₹12,000, range ₹2K-₹1L)
    credit_limits = {}
    for cid in customer_ids:
        if cid in credit_set:
            lim = float(rng.lognormal(mean=9.4, sigma=0.9))
            lim = round(max(2000.0, min(100000.0, lim)), -2)  # round to nearest 100
        else:
            lim = 0.0
        credit_limits[str(cid)] = lim

    # Customer join day: 20% join yr1, rest spread across years 1-9
    join_days = {}
    for cid in customer_ids:
        if rng.random() < 0.20:
            jd = int(rng.integers(0, 365))
        else:
            jd = int(rng.integers(0, 3285))
        join_days[str(cid)] = jd

    # Churn & temp churn
    churn_days = {}
    temp_churn = {}
    n_perm_churn = int(n_cust * 0.15)
    n_temp_churn = int(n_cust * 0.10)
    idx_arr  = list(range(n_cust))
    rng.shuffle(idx_arr)
    perm_idx = set(idx_arr[:n_perm_churn])
    temp_idx = set(idx_arr[n_perm_churn: n_perm_churn + n_temp_churn])

    for i, cid in enumerate(customer_ids):
        if i in perm_idx:
            churn_days[str(cid)] = int(rng.integers(365, 2920))
        elif i in temp_idx:
            start = int(rng.integers(200, 2500))
            dur   = int(rng.integers(180, 540))
            temp_churn[str(cid)] = [start, start + dur]

    # ── Combo pairs (FP-Growth signal) ────────────────────────────────────
    COMBO_PAIRS_NAMES = [
        ("Maggi", "Britannia"), ("Maggi", "Amul"), ("Maggi", "Tata Salt"),
        ("Lays",  "Coca Cola"), ("Lays",  "Pepsi"), ("Lays", "Kurkure"),
        ("Kurkure","Pepsi"),    ("Sprite","Haldiram"),
        ("Britannia","Mother Dairy"), ("Parle","Amul"),
        ("Tata Salt","Aashirvaad"), ("Fortune","Aashirvaad"),
        ("Colgate","Lux"), ("Top Ramen","Yippee"),
    ]
    combo_pairs = []
    for pa, pb in COMBO_PAIRS_NAMES:
        va = product_to_variants.get(pa, [])
        vb = product_to_variants.get(pb, [])
        # fuzzy match if exact not found
        if not va:
            va = [v for pn, vlist in product_to_variants.items() if pa.lower() in pn.lower() for v in vlist]
        if not vb:
            vb = [v for pn, vlist in product_to_variants.items() if pb.lower() in pn.lower() for v in vlist]
        if va and vb:
            combo_pairs.append([va[:5], vb[:5]])

    categories_list = list(CATALOG.keys())

    maps = {
        "all_variant_ids":          all_variant_ids,
        "variant_price_map":        variant_price_map,
        "variant_opening_stock":    variant_opening_stock,
        "variant_to_product_name":  variant_to_product,
        "variant_to_category":      variant_to_category,
        "variant_reorder_point":    variant_reorder_point,
        "product_name_to_variant_ids": {k: v for k, v in product_to_variants.items()},
        "category_to_variant_ids":  {k: v for k, v in cat_to_variants.items()},
        "supplier_ids":             supplier_ids,
        "supplier_category_map":    supplier_cat_map,
        "customer_ids":             customer_ids,
        "credit_customer_ids":      credit_customer_ids,
        "credit_limits":            credit_limits,
        "customer_join_day":        join_days,
        "customer_segments":        customer_segments,
        "churn_days":               churn_days,
        "temp_churn":               temp_churn,
        "combo_pairs":              combo_pairs,
        "categories":               categories_list,
    }

    meta = {
        "total_products":  c.execute("SELECT COUNT(*) FROM product").fetchone()[0],
        "total_variants":  c.execute("SELECT COUNT(*) FROM product_variant").fetchone()[0],
        "total_customers": len(customer_ids),
        "total_suppliers": len(supplier_ids),
        "credit_customers": len(credit_customer_ids),
        "categories":      categories_list,
        "generated_at":    datetime.now().isoformat(),
    }

    with open(MAPS_PATH, "w") as f:
        json.dump(maps, f)
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"   ✅ Maps → {MAPS_PATH}")
    print(f"   ✅ Meta → {META_PATH}")
    return maps, meta


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    rng = np.random.default_rng(RNG_SEED)

    print("=" * 60)
    print("  NexusRetailOS — STEP 1: Master Data Generator")
    print(f"  DB: {DB_PATH}")
    print("=" * 60)

    # Guard: check if already seeded
    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='product'").fetchone()[0]
    if existing:
        count = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]
        if count > 100:
            print(f"\n⚠️  Database already has {count} products. Skipping master data generation.")
            print("   Delete nexus.db to re-seed from scratch.")
            conn.close()
            return

    create_tables(conn)
    pid_map       = generate_products(conn, rng)
    customer_rows = generate_customers(conn, rng)
    supplier_rows = generate_suppliers(conn, rng)
    maps, meta    = build_and_save_maps(conn, customer_rows, supplier_rows, rng)

    # Indexes created here — BEFORE transactions so they're ready
    # (We skip index creation here; transactions script will do it AFTER inserts)
    conn.commit()
    conn.close()

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  ✅  STEP 1 COMPLETE  ({elapsed:.1f}s)")
    print(f"     Products  : {meta['total_products']:,}  ({meta['total_variants']:,} variants)")
    print(f"     Customers : {meta['total_customers']:,}  ({meta['credit_customers']:,} credit)")
    print(f"     Suppliers : {meta['total_suppliers']:,}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
