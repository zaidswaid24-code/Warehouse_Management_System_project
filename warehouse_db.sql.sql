create database warehouseDB;
use warehouseDB;
create table warehouse(warehouseID int , warehouseName varchar(20),location varchar(20));
create table product(productID int , productName varchar(20),price int ,category varchar(20));
create table supplier(supplierID int , supplierName varchar(20),phone int , email varchar(40));
create table stock(stockID int , warehouseID int, productID int , quantity int );
create table transfer(transferID int , from_warehouseID int , to_warehouseID int , transferData int );
create table transferDetails(transfer_DetailID int , transferID int , productID int , quantity int );

INSERT INTO warehouse VALUES
(1, 'Main Warehouse', 'Sanaa'),
(2, 'North Warehouse', 'Aden'),
(3, 'South Warehouse', 'Taiz');
select * from warehouse;

INSERT INTO product VALUES
(101, 'Laptop', 800, 'Electronics'),
(102, 'Mouse', 20, 'Accessories'),
(103, 'Keyboard', 35, 'Accessories'),
(104, 'Monitor', 250, 'Electronics');
select * from product;


INSERT INTO supplier VALUES
(1, 'Tech Store', 777111111, 'tech@gmail.com'),
(2, 'Computer World', 777222222, 'computer@gmail.com'),
(3, 'Global Supplier', 777333333, 'global@gmail.com');
select * from supplier;

select * from supplier;

INSERT INTO stock VALUES
(1, 1, 101, 20),
(2, 1, 102, 50),
(3, 2, 103, 40),
(4, 3, 104, 15);
select * from stock;


INSERT INTO transfer VALUES
(1, 1, 2, 20250820),
(2, 2, 3, 20250821);
select * from transfer;

INSERT INTO transferDetails VALUES
(1, 1, 101, 5),
(2, 1, 102, 10),
(3, 2, 103, 8);

select * from transferDetails;
ALTER TABLE warehouse ADD PRIMARY KEY (warehouseID);
ALTER TABLE product ADD PRIMARY KEY (productID);
ALTER TABLE supplier ADD PRIMARY KEY (supplierID);
ALTER TABLE stock ADD PRIMARY KEY (stockid);
ALTER TABLE transfer ADD PRIMARY KEY (transferID);
ALTER TABLE transferDetails ADD PRIMARY KEY (transfer_Detailid);

alter table stock add constraint fk_stock_warehouse foreign key (warehouseid) references warehouse(warehouseid);
alter table stock add constraint fk_stock_product foreign key (productid) references product(productid);

ALTER TABLE transfer
ADD CONSTRAINT fk_transfer_from
FOREIGN KEY (from_warehouseID)
REFERENCES warehouse(warehouseID);

ALTER TABLE transfer
ADD CONSTRAINT fk_transfer_to
FOREIGN KEY (to_warehouseID)
REFERENCES warehouse(warehouseID);

ALTER TABLE transferDetails
ADD CONSTRAINT fk_transferDetails_transfer
FOREIGN KEY (transferID)
REFERENCES transfer(transferID);

ALTER TABLE transferDetails
ADD CONSTRAINT fk_transferDetails_product
FOREIGN KEY (productID)
REFERENCES product(productID);

UPDATE stock
SET quantity = 30
WHERE stockID = 1;

DELETE FROM stock
WHERE stockID = 4;

SELECT
    p.productName,
    w.warehouseName,
    s.quantity
FROM stock s
JOIN product p ON s.productID = p.productID
JOIN warehouse w ON s.warehouseID = w.warehouseID;
use warehousedb;

ALTER TABLE product
ADD supplierID INT;

ALTER TABLE product
ADD CONSTRAINT fk_product_supplier
FOREIGN KEY (supplierID)
REFERENCES supplier(supplierID);


UPDATE product
SET supplierID = 1
WHERE productID = 101;

UPDATE product
SET supplierID = 2
WHERE productID = 102;

UPDATE product
SET supplierID = 3
WHERE productID = 103;

UPDATE product
SET supplierID = 1
WHERE productID = 104;


use warehousedb;
show create table transferDetails;
select * from transferDetails;
select * from stock;

INSERT INTO transferDetails
VALUES (4,2,104,7);

describe stock;


ALTER TABLE stock
ADD COLUMN binLocation VARCHAR(50);

UPDATE stock
SET binLocation = 'A-01'
WHERE stockID = 1;

UPDATE stock
SET binLocation = 'B-02'
WHERE stockID = 2;


select * from transfer;
select * from transferDetails;

ALTER TABLE transfer
ADD COLUMN status VARCHAR(20) DEFAULT 'Pending';

SET SQL_SAFE_UPDATES = 0;

UPDATE transfer
SET status = 'Pending'
WHERE status IS NULL;

CREATE TABLE dispatch (
    dispatchID INT PRIMARY KEY AUTO_INCREMENT,
    productID INT NOT NULL,
    quantity INT NOT NULL,
    destination VARCHAR(100) NOT NULL,
    dispatchDate DATE NOT NULL
);

INSERT INTO dispatch (productID, quantity, destination, dispatchDate)
VALUES
(101, 5, 'Warehouse 2', '2025-08-20'),
(102, 10, 'Warehouse 3', '2025-08-21');

CREATE TABLE damagedStock (
    damageID INT PRIMARY KEY,
    stockID INT,
    quantity INT,
    reason VARCHAR(255),
    damageDate DATE,
    FOREIGN KEY (stockID) REFERENCES stock(stockID)
);

CREATE TABLE reconciliation (
    reconID INT PRIMARY KEY,
    stockID INT,
    systemQty INT,
    countedQty INT,
    difference INT,
    reconDate DATE,
    note VARCHAR(255),
    FOREIGN KEY (stockID) REFERENCES stock(stockID)
);

INSERT INTO damagedStock
VALUES
(1,1,2,'Broken','2025-08-20'),
(2,2,1,'Expired','2025-08-21');


INSERT INTO reconciliation
VALUES
(1,1,50,48,-2,'2025-08-20','Inventory count'),
(2,2,30,30,0,'2025-08-21','OK');




DESCRIBE DISPATCH;

DROP TABLE IF EXISTS dispatch;

CREATE TABLE dispatch (
    dispatchID INT AUTO_INCREMENT PRIMARY KEY,
    stockID INT NOT NULL,
    quantity INT NOT NULL,
    destination VARCHAR(100) NOT NULL,
    dispatchDate DATE NOT NULL,
    FOREIGN KEY (stockID) REFERENCES stock(stockID)
);
use warehousedb;









