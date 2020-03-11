
/****************************************************
 * Program to read IBM 5100 C4 Basic card
 * Author: Patrick Lessard
 * Date: March 8th 2020
 * Note: Address and control lines are active Low
 */

// Pin assignment

// Address pins
static const byte aPin_A0 = PIN_B6;
static const byte aPin_A1 = PIN_B5;
static const byte aPin_A2 = PIN_B4;
static const byte aPin_A3 = PIN_B3;
static const byte aPin_A4 = PIN_B2;
static const byte aPin_A5 = PIN_B1;
static const byte aPin_A6 = PIN_B0;
static const byte aPin_A7 = PIN_C7;
static const byte aPin_A8 = PIN_C6;
static const byte aPin_A9 = PIN_C5;
static const byte aPin_A10 = PIN_C4;
static const byte aPin_A11 = PIN_C3;
static const byte aPin_A12 = PIN_C2;
static const byte aPin_A13 = PIN_C1;
static const byte aPin_A14 = PIN_C0;


// Data pins
static const byte dPin_D0 = PIN_D0;
static const byte dPin_D1 = PIN_D1;
static const byte dPin_D2 = PIN_D2;
static const byte dPin_D3 = PIN_D3;
static const byte dPin_D4 = PIN_D4;
static const byte dPin_D5 = PIN_D5;
static const byte dPin_D6 = PIN_D6;
static const byte dPin_D7 = PIN_D7;

// Control pins
static const byte cPin_ROS_Restart = PIN_E0;
static const byte cPin_ROS_Set = PIN_E1;
static const byte cPin_ROS_Low_Bytes = PIN_E6;
static const byte cPin_ROS_High_Bytes = PIN_E7;
static const byte cPin_ROS_SampleReset = PIN_B7;

// Set Address on address bus
void SetAddress(unsigned int addr) {
  
   // update the address lines to reflect the address we want ...
   digitalWrite(aPin_A0, (addr & 1)?LOW:HIGH);
   digitalWrite(aPin_A1, (addr & 2)?LOW:HIGH);
   digitalWrite(aPin_A2, (addr & 4)?LOW:HIGH);
   digitalWrite(aPin_A3, (addr & 8)?LOW:HIGH);
   digitalWrite(aPin_A4, (addr & 16)?LOW:HIGH);
   digitalWrite(aPin_A5, (addr & 32)?LOW:HIGH);
   digitalWrite(aPin_A6, (addr & 64)?LOW:HIGH);
   digitalWrite(aPin_A7, (addr & 128)?LOW:HIGH);
   digitalWrite(aPin_A8, (addr & 256)?LOW:HIGH);
   digitalWrite(aPin_A9, (addr & 512)?LOW:HIGH);
   digitalWrite(aPin_A10, (addr & 1024)?LOW:HIGH);
   digitalWrite(aPin_A11, (addr & 2048)?LOW:HIGH);
   digitalWrite(aPin_A12, (addr & 4096)?LOW:HIGH);
   digitalWrite(aPin_A13, (addr & 8192)?LOW:HIGH);
   digitalWrite(aPin_A14, (addr & 16384)?LOW:HIGH);
}

// Read byte from data bus
byte ReadByte() {

   // read the current 8-bit byte being output by the ROM ...
   byte b = 0;
   
   digitalWrite(cPin_ROS_SampleReset, LOW);
   delay(1);
   if (digitalRead(dPin_D0)) b |= 1;
   if (digitalRead(dPin_D1)) b |= 2;
   if (digitalRead(dPin_D2)) b |= 4;
   if (digitalRead(dPin_D3)) b |= 8;
   if (digitalRead(dPin_D4)) b |= 16;
   if (digitalRead(dPin_D5)) b |= 32;
   if (digitalRead(dPin_D6)) b |= 64;
   if (digitalRead(dPin_D7)) b |= 128;
   delay(1);
   digitalWrite(cPin_ROS_SampleReset, HIGH);
   
   return (b);
}

// Compare file with ROM
void CompareFileROM(unsigned int size) {
  
  boolean flag = true;
  byte d[size], b;
  unsigned int addr = 0;
 
  Serial.println("\n");
  Serial.println("Comparing ROM ...");
  Serial.println("Waiting for data ...");

  // Reading file into buffer
  while (addr < size) {
    if (Serial.available()) {
      d[addr] = Serial.read();
      addr++;
    }
  }
  // Comparing file with ROM
  addr = 0;
  while (addr < size) {
    SetAddress(addr);
    b = ReadByte();
    if (b != d[addr]) {
       Serial.printf("Verify Error at address: %04X", addr);
       Serial.println("");
       flag = false;
    }
    addr++;
  }
  Serial.println("");
  if (flag)
    Serial.println("Verify OK!");
  else
    Serial.println("Verify Error");
}


// Read ROM and display on Serial
void ReadROM(unsigned int size) {
   byte d[16], x, y;
   unsigned int addr;
 
   Serial.println("\n");
   Serial.println("Reading ROM ...");

   for (addr = 0; addr < size; addr += 16) {
     // read 16 bytes of data from the ROM ...
     for (x = 0; x < 16; x++) {
       SetAddress(addr + x);
       d[x] = ReadByte();
     }
 
     // now we'll print each byte in hex ...
     Serial.printf("%04X:", addr);
     for (y = 0; y < 16; y++)
       Serial.printf("%02X", d[y]);
 
     // and print an ASCII dump too ...
 
     Serial.print(" ");
     for (y = 0; y < 16; y++) {
       char c = '.';
       if (d[y] > 32 && d[y]<127) c = d[y];
       Serial.print(c);
     }
     Serial.println("");
   }
}

// Read ROM binary mode and display on Serial
void ReadROMBinary(unsigned int size) {
   unsigned int addr;
 

   Serial.println("\n");
   Serial.println("Reading ROM ...");
 
   for (addr = 0; addr < size; addr ++) {
       SetAddress(addr);
       Serial.printf("%02X", ReadByte());
   }
}

// Display Menu
void DisplayMenu() {
  unsigned char c;
  unsigned int size = 1024;
  
  Serial.println("\n");
  Serial.println("IBM 5100 C4 Basic ROM Card Menu");
  Serial.println("------------------------");
  Serial.print("ROM Size: ");
  Serial.println(size);
  Serial.println("(1)Read ROM");
  Serial.println("(2)Read ROM Binary mode");
  Serial.println("(3)Compare ROM with file");
  Serial.println("----------------------------");
  Serial.print("Press the corresponding key:");
  while (!Serial.available());
  c = Serial.read();
  switch (c) {
    case '1':
      ReadROM(size);
      break;
    case '2':
      ReadROMBinary(size);
      break;
    case '3':
      CompareFileROM(size);
      break;
    default:
      Serial.println("");
      Serial.println("Please choose a valid option");
      break;
  }
}
 
// Setup
void setup() { 
   // Set the address lines as outputs ...
   pinMode(aPin_A0, OUTPUT);
   pinMode(aPin_A1, OUTPUT);
   pinMode(aPin_A2, OUTPUT);
   pinMode(aPin_A3, OUTPUT);
   pinMode(aPin_A4, OUTPUT);
   pinMode(aPin_A5, OUTPUT);
   pinMode(aPin_A6, OUTPUT);
   pinMode(aPin_A7, OUTPUT);
   pinMode(aPin_A8, OUTPUT);
   pinMode(aPin_A9, OUTPUT);
   pinMode(aPin_A10, OUTPUT);
   pinMode(aPin_A11, OUTPUT);
   pinMode(aPin_A12, OUTPUT);
   pinMode(aPin_A13, OUTPUT);
   pinMode(aPin_A14, OUTPUT);

   // set data pins as input...
   pinMode(dPin_D0, INPUT);
   pinMode(dPin_D1, INPUT);
   pinMode(dPin_D2, INPUT);
   pinMode(dPin_D3, INPUT);
   pinMode(dPin_D4, INPUT);
   pinMode(dPin_D5, INPUT);
   pinMode(dPin_D6, INPUT);
   pinMode(dPin_D7, INPUT);
  
   // set the control lines as outputs ...
   pinMode(cPin_ROS_Restart, OUTPUT);
   pinMode(cPin_ROS_Set, OUTPUT);
   pinMode(cPin_ROS_Low_Bytes, OUTPUT);
   pinMode(cPin_ROS_High_Bytes, OUTPUT);
   pinMode(cPin_ROS_SampleReset, OUTPUT);

   //set control lines
   digitalWrite(cPin_ROS_Restart, HIGH);
   digitalWrite(cPin_ROS_Set, LOW);

   digitalWrite(cPin_ROS_Low_Bytes, LOW);
   digitalWrite(cPin_ROS_High_Bytes, HIGH);
   digitalWrite(cPin_ROS_SampleReset, HIGH);

   Serial.begin(9600);
}

// Main loop
void loop() {
  DisplayMenu();
}
// End of program
