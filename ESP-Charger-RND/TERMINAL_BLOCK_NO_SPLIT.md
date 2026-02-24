# Terminal Block Setup - Tanpa Split Wire

## Masalah: Wire CP Tak Boleh Split!

**Wire CP dari charger = 1 wire sahaja, tak boleh split!**

**Solution: Guna Wire Jumper!** ✅

---

## Setup dengan Terminal Block Anda

### Berdasarkan Gambar (Red Wire dah connect ke Terminal 6):

**Terminal Block Structure:**
```
Top Row:
┌─────────┬─────────┬─────────┐
│    1    │    2    │    3    │
└─────────┴─────────┴─────────┘

Bottom Row:
┌─────────┬─────────┬─────────┐
│    4    │    5    │    6    │
│         │         │  Red    │ ←── Red Wire dah connect di sini!
│         │         │  Wire   │
└─────────┴─────────┴─────────┘
```

---

## Setup dengan Wire Jumper (Tanpa Split!)

### Terminal 6 sebagai Connection Point:

```
Terminal 6 (Bottom Row):
┌─────────┐
│    6    │ ←── Red Wire (CP dari charger) - dah connect!
└─────────┘
    │
    ├──> Wire Jumper 1 ──> Terminal 1 (Top) ──> CP_OUT wire
    │
    └──> Wire Jumper 2 ──> Terminal 4 (Bottom) ──> CP_IN wire
```

**Key Point:** Red Wire **TIDAK PERLU SPLIT!** Guna wire jumper sahaja!

---

## Step-by-Step Setup

### Step 1: Terminal 6 (Red Wire - Dah Connect!)

**Status:** ✅ Dah connect (dari gambar)

- Red Wire (CP dari charger) dah connect ke Terminal 6
- Ketatkan screw kalau belum ketat
- Verify: Wire kuat, tak longgar

---

### Step 2: Terminal 1 (CP_OUT)

**Setup:**
```
Terminal 1 (Top Row):
┌─────────┐
│    1    │ ←── CP_OUT wire (ke breadboard)
└─────────┘
    │
    └──> Wire Jumper dari Terminal 6
```

**Cara:**
1. Ambil **CP_OUT wire** (dari breadboard Row 11, Column E)
2. Strip wire sedikit (buang insulation)
3. Masukkan ke **Terminal 1 (Top Row)**, ketatkan screw
4. Ambil **wire jumper** (wire pendek, contoh 5-10cm)
5. Strip kedua-dua hujung wire jumper
6. Masukkan satu hujung ke **Terminal 6**, ketatkan screw
7. Masukkan hujung satu lagi ke **Terminal 1** (sama terminal dengan CP_OUT wire), ketatkan screw
8. **✅ Terminal 1 complete!** CP_OUT connected ke Red Wire via wire jumper!

---

### Step 3: Terminal 4 (CP_IN)

**Setup:**
```
Terminal 4 (Bottom Row):
┌─────────┐
│    4    │ ←── CP_IN wire (dari breadboard)
└─────────┘
    │
    └──> Wire Jumper dari Terminal 6
```

**Cara:**
1. Ambil **CP_IN wire** (ke breadboard Row 17, Column A)
2. Strip wire sedikit (buang insulation)
3. Masukkan ke **Terminal 4 (Bottom Row)**, ketatkan screw
4. Ambil **wire jumper** (wire pendek, contoh 5-10cm)
5. Strip kedua-dua hujung wire jumper
6. Masukkan satu hujung ke **Terminal 6**, ketatkan screw
7. Masukkan hujung satu lagi ke **Terminal 4** (sama terminal dengan CP_IN wire), ketatkan screw
8. **✅ Terminal 4 complete!** CP_IN connected ke Red Wire via wire jumper!

---

## Visual Setup Complete

### Terminal Block Layout:

```
Top Row:
┌─────────┬─────────┬─────────┐
│    1    │    2    │    3    │
│ CP_OUT  │ (kosong)│ (kosong)│
│  wire   │         │         │
│  +      │         │         │
│ jumper  │         │         │
└─────────┴─────────┴─────────┘
    │
    │ Wire Jumper 1
    │
Bottom Row:
┌─────────┬─────────┬─────────┐
│    4    │    5    │    6    │
│ CP_IN   │ (kosong)│  Red    │ ←── Connection point!
│  wire   │         │  Wire   │
│  +      │         │  (CP)   │
│ jumper  │         │         │
└─────────┴─────────┴─────────┘
    │              │
    │ Wire Jumper 2│
    └──────────────┘
```

---

## Wire Jumper Details

### Wire Jumper = Wire Pendek untuk Connect Terminal

**Specifications:**
- **Length:** 5-10cm (pendek sahaja)
- **Gauge:** Same dengan CP_OUT/CP_IN wire (contoh: AWG 22-18)
- **Material:** Same dengan wires lain (copper wire)
- **Insulation:** Optional (boleh guna bare wire atau insulated)

**Function:**
- Connect Terminal 6 (Red Wire) ke Terminal 1 (CP_OUT)
- Connect Terminal 6 (Red Wire) ke Terminal 4 (CP_IN)
- **Red Wire TIDAK PERLU SPLIT!** ✅

---

## Complete Connection Diagram

### Full Setup:

```
Charger
  │
  │ Red Wire (CP) - TIDAK SPLIT!
  │
  └──> Terminal 6 (Bottom Row)
          │
          ├──> Wire Jumper 1 ──> Terminal 1 (Top) ──> CP_OUT wire ──> Breadboard
          │
          └──> Wire Jumper 2 ──> Terminal 4 (Bottom) ──> CP_IN wire ──> Breadboard
```

**Key Point:**
- Red Wire = 1 wire sahaja, connect ke Terminal 6
- Wire Jumper 1 = Terminal 6 → Terminal 1 (CP_OUT)
- Wire Jumper 2 = Terminal 6 → Terminal 4 (CP_IN)
- **TIDAK PERLU SPLIT RED WIRE!** ✅

---

## Alternative Setup (Kalau Terminal 6 Penuh)

### Guna Terminal Lain sebagai Connection Point:

**Kalau Terminal 6 dah penuh atau tak boleh guna:**

**Option A: Guna Terminal 1 sebagai Connection Point**
```
Terminal 1 (Top): Red Wire (CP) + CP_OUT wire + Wire jumper ke Terminal 4
Terminal 4 (Bottom): CP_IN wire + Wire jumper dari Terminal 1
```

**Option B: Guna Terminal 3 sebagai Connection Point**
```
Terminal 3 (Top): Red Wire (CP) + Wire jumper ke Terminal 1 & 4
Terminal 1 (Top): CP_OUT wire + Wire jumper dari Terminal 3
Terminal 4 (Bottom): CP_IN wire + Wire jumper dari Terminal 3
```

---

## Checklist Setup

### Terminal 6 (Red Wire):
- [x] Red Wire dah connect (dari gambar)
- [ ] Verify: Screw ketat, wire kuat

### Terminal 1 (CP_OUT):
- [ ] Strip CP_OUT wire
- [ ] Masukkan ke Terminal 1, ketatkan screw
- [ ] Strip wire jumper (5-10cm)
- [ ] Connect Terminal 6 → Terminal 1 dengan wire jumper
- [ ] Verify: CP_OUT connected ke Red Wire

### Terminal 4 (CP_IN):
- [ ] Strip CP_IN wire
- [ ] Masukkan ke Terminal 4, ketatkan screw
- [ ] Strip wire jumper (5-10cm)
- [ ] Connect Terminal 6 → Terminal 4 dengan wire jumper
- [ ] Verify: CP_IN connected ke Red Wire

**✅ Complete!**

---

## Summary

**Problem:** Wire CP dari charger tak boleh split
**Solution:** Guna wire jumper! ✅

**Setup:**
- **Terminal 6:** Red Wire (CP dari charger) - dah connect!
- **Terminal 1:** CP_OUT wire + Wire jumper dari Terminal 6
- **Terminal 4:** CP_IN wire + Wire jumper dari Terminal 6

**Wire jumper = wire pendek untuk connect Terminal 6 ke Terminal 1 & 4**

**Red Wire TIDAK PERLU SPLIT!** ✅

---

## Final Answer

**Ya, boleh guna terminal block tanpa split red wire!**

**Guna wire jumper untuk connect:**
- Terminal 6 (Red Wire) → Terminal 1 (CP_OUT)
- Terminal 6 (Red Wire) → Terminal 4 (CP_IN)

**Wire jumper = wire pendek (5-10cm) untuk connect terminal**

**Setup dah siap, boleh proceed!** ✅







