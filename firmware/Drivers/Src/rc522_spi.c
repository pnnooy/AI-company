#include "rc522_spi.h"
#include "stm32f1xx_hal.h"
#include "spi.h"

/* Direct register access for speed — HAL_GPIO_WritePin is ~30-40 cycles
   and too slow for CS toggling at 8 MHz SPI (one bit = 0.125 us).
   BSRR/BRR are single-cycle atomic bit-set / bit-reset.
   cs_pulse() ensures minimum CS high time (~2 us) between SPI frames
   so the MFRC522 can internally process the previous byte.
   The delay after CS_LOW (~500 ns) gives the MFRC522's SPI receiver
   time to settle before the first SCK edge.                           */
static void cs_pulse(void) {
    for (volatile uint32_t i = 0; i < 30; i++) { __NOP(); }
}
#define CS_LOW()   do { GPIOA->BRR  = GPIO_PIN_4; cs_pulse(); } while(0)
#define CS_HIGH()  do { GPIOA->BSRR = GPIO_PIN_4; cs_pulse(); } while(0)
#define RST_LOW()  do { GPIOA->BRR  = GPIO_PIN_3; } while(0)
#define RST_HIGH() do { GPIOA->BSRR = GPIO_PIN_3; } while(0)

/* HAL_Delay-free busy-wait (project rule: no HAL_Delay) */
static void delay_ms(uint32_t ms) {
    uint32_t tickstart = HAL_GetTick();
    while ((HAL_GetTick() - tickstart) < ms) { /* spin */ }
}

/* MFRC522 registers */
enum {
    CommandReg     = 0x01,
    ComIEnReg      = 0x02,
    DivIEnReg      = 0x03,
    ComIrqReg      = 0x04,
    DivIrqReg      = 0x05,
    ErrorReg       = 0x06,
    Status2Reg     = 0x08,
    FIFODataReg    = 0x09,
    FIFOLevelReg   = 0x0A,
    ControlReg     = 0x0C,
    BitFramingReg  = 0x0D,
    CollReg        = 0x0E,
    ModeReg        = 0x11,
    TxControlReg   = 0x14,
    TxAutoReg      = 0x15,
    RxSelReg       = 0x17,
    RFCfgReg       = 0x26,
    CRCResultRegH  = 0x21,
    CRCResultRegL  = 0x22,
    TModeReg       = 0x2A,
    TPrescalerReg  = 0x2B,
    TReloadRegH    = 0x2C,
    TReloadRegL    = 0x2D,
    VersionReg     = 0x37,
};

/* MFRC522 commands */
#define PCD_IDLE       0x00
#define PCD_CALCCRC    0x03
#define PCD_TRANSCEIVE 0x0C
#define PCD_SOFTRESET  0x0F

/* PICC commands */
#define PICC_REQA      0x26
#define PICC_WUPA      0x52
#define PICC_ANTICOLL  0x93
#define PICC_SELECT    0x93
#define PICC_HALT      0x50

/* ------------------------------------------------------------------ */
/* SPI R/W (same verified code)                                       */
/* ------------------------------------------------------------------ */

uint8_t RC522_ReadReg(uint8_t reg) {
    uint8_t tx[2], rx[2];
    tx[0] = ((reg << 1) & 0x7E) | 0x80;  /* address byte: read (MSB=1) */
    tx[1] = 0x00;                          /* dummy byte to clock out data  */
    CS_LOW();
    __disable_irq();
    HAL_SPI_TransmitReceive(&hspi1, tx, rx, 2, 100);
    __enable_irq();
    CS_HIGH();
    return rx[1];  /* register value arrives on the second byte */
}

void RC522_WriteReg(uint8_t reg, uint8_t val) {
    uint8_t tx[2];
    tx[0] = ((reg << 1) & 0x7E);          /* address byte: write (MSB=0) */
    tx[1] = val;                           /* data byte                    */
    CS_LOW();
    __disable_irq();
    HAL_SPI_Transmit(&hspi1, tx, 2, 100);
    __enable_irq();
    CS_HIGH();
}

static void SetBitMask(uint8_t reg, uint8_t mask) {
    RC522_WriteReg(reg, RC522_ReadReg(reg) | mask);
}

static void ClearBitMask(uint8_t reg, uint8_t mask) {
    RC522_WriteReg(reg, RC522_ReadReg(reg) & ~mask);
}

/* ------------------------------------------------------------------ */
/* Antenna ON / OFF                                                   */
/* ------------------------------------------------------------------ */

static void AntennaOn(void) {
    uint8_t v = RC522_ReadReg(TxControlReg);
    if (!(v & 0x03)) {
        SetBitMask(TxControlReg, 0x03);
    }
}

/* ------------------------------------------------------------------ */
/* Reset & Init                                                       */
/* ------------------------------------------------------------------ */

static void RC522_HardReset(void) {
    RST_HIGH();
    delay_ms(10);
    RST_LOW();
    delay_ms(10);
    RST_HIGH();
    delay_ms(50);

    /* Soft reset */
    RC522_WriteReg(CommandReg, PCD_SOFTRESET);
    delay_ms(50);

    /* Timer: TAuto=1 */
    RC522_WriteReg(TModeReg, 0x8D);
    RC522_WriteReg(TPrescalerReg, 0x3E);
    RC522_WriteReg(TReloadRegH, 0x00);
    RC522_WriteReg(TReloadRegL, 0x1E);

    /* 106 kbps, CRC preset */
    RC522_WriteReg(TxAutoReg, 0x40);
    RC522_WriteReg(ModeReg, 0x3D);

    /* NOTE: RFCfgReg and RxSelReg are left at power-on defaults:
       RFCfgReg = 0x48 (18 dB Rx gain) — stable for continuous polling
       RxSelReg = 0x84 (default)        — max gain (0x7F / 48 dB)
       caused TemperatureErr and spontaneous reset under 48 % TX duty cycle */

    /* Reduce RF power to prevent spontaneous reset on weak power supply */
    RC522_WriteReg(RFCfgReg, 0x48);   /* 18 dB - conservative, stable */
    RC522_WriteReg(RxSelReg, 0x84);   /* default Rx gain */

    /* Antenna on */
    AntennaOn();
}

uint8_t RC522_Init(void) {
    RC522_HardReset();

    /* Drop SPI clock to 2 MHz (prescaler /32 from 64 MHz APB2).
       MFRC522 datasheet says 10 MHz max, but many clone modules
       are unreliable above 4 MHz.  2 MHz is still >10x faster
       than the 106 kbps RF data rate, so NFC performance is
       unaffected — only register R/W slows down negligibly.     */
    CLEAR_BIT(SPI1->CR1, SPI_CR1_BR);
    SET_BIT(SPI1->CR1, SPI_BAUDRATEPRESCALER_32);

    /* Verify SPI link: read version register twice — they must match */
    uint8_t v1 = RC522_ReadReg(VersionReg);
    uint8_t v2 = RC522_ReadReg(VersionReg);
    if (v1 != v2 || (v1 != 0x92 && v1 != 0x91 && v1 != 0x88)) {
        return 0;  /* SPI unreliable or chip absent */
    }
    return 1;
}

uint8_t RC522_GetVersion(void) {
    return RC522_ReadReg(VersionReg);
}

/* ------------------------------------------------------------------ */
/* Transceive (send + receive)                                        */
/* ------------------------------------------------------------------ */

static uint8_t RC522_Transceive(uint8_t *sendData, uint8_t sendLen,
                                 uint8_t *backData, uint8_t *backLen,
                                 uint8_t validBits)
{
    uint8_t wait_irq = 0x30;  /* RxIrq | IdleIrq */

    /* Bit framing: last byte has validBits valid bits */
    RC522_WriteReg(BitFramingReg, validBits);

    /* Cancel any running command */
    RC522_WriteReg(CommandReg, PCD_IDLE);

    /* Clear pending interrupts */
    RC522_WriteReg(ComIrqReg, 0x7F);
    RC522_WriteReg(DivIrqReg, 0x80);

    /* Flush FIFO */
    SetBitMask(FIFOLevelReg, 0x80);

    /* Enable all interrupts */
    RC522_WriteReg(ComIEnReg, 0x7F);
    RC522_WriteReg(DivIEnReg, 0x80);

    /* Write data to FIFO */
    for (uint8_t i = 0; i < sendLen; i++) {
        RC522_WriteReg(FIFODataReg, sendData[i]);
    }

    /* Start Transceive */
    RC522_WriteReg(CommandReg, PCD_TRANSCEIVE);
    SetBitMask(BitFramingReg, 0x80);  /* StartSend */

    /* Wait for RxIrq, IdleIrq, or TimerIrq */
    uint16_t cnt = 2000;
    uint8_t n;
    do {
        n = RC522_ReadReg(ComIrqReg);
        cnt--;
    } while ((cnt != 0) && !(n & 0x01) && !(n & wait_irq));

    /* Clear StartSend */
    ClearBitMask(BitFramingReg, 0x80);

    /* Timeout or hardware error */
    if (cnt == 0 || (RC522_ReadReg(ErrorReg) & 0x1B)) {
        goto cleanup;
    }

    /* RxIRq (bit 5) must be set — TxIRq or TimerIRq alone = no card */
    if (!(n & 0x20)) {
        goto cleanup;
    }

    /* Read received data */
    uint8_t fifo_bytes = RC522_ReadReg(FIFOLevelReg);
    uint8_t last_bits  = RC522_ReadReg(ControlReg) & 0x07;  /* RxLastBits, NOT CollReg */

    /* Clamp FIFO byte count BEFORE computing backLen */
    if (fifo_bytes == 0) fifo_bytes = 1;
    if (fifo_bytes > 16) fifo_bytes = 16;

    if (last_bits)
        *backLen = (fifo_bytes - 1) * 8 + last_bits;
    else
        *backLen = fifo_bytes * 8;

    for (uint8_t i = 0; i < fifo_bytes; i++) {
        backData[i] = RC522_ReadReg(FIFODataReg);
    }

    /* Post-transceive cleanup: stop timer, return to idle */
    SetBitMask(ControlReg, 0x80);     /* TStopNow */
    RC522_WriteReg(CommandReg, PCD_IDLE);
    /* Dummy read to stabilise SPI link for next transaction */
    RC522_ReadReg(VersionReg);
    return 1;

cleanup:
    SetBitMask(ControlReg, 0x80);
    RC522_WriteReg(CommandReg, PCD_IDLE);
    RC522_ReadReg(VersionReg);
    return 0;
}

/* ------------------------------------------------------------------ */
/* SPI warm-up — call before any multi-register read sequence         */
/* (nfcdbg, etc.) to avoid first-byte glitch                          */
/* ------------------------------------------------------------------ */
void RC522_Wakeup(void) {
    CS_LOW();
    cs_pulse();                     /* extra CS setup */
    uint8_t dummy = 0xFF;
    HAL_SPI_Transmit(&hspi1, &dummy, 1, 10);
    CS_HIGH();
}

/* ------------------------------------------------------------------ */
/* High-level card operations                                         */
/* ------------------------------------------------------------------ */

uint8_t RC522_CheckCard(void) {
    uint8_t back[16];
    uint8_t backLen = 0;
    uint8_t cmd = PICC_REQA;

    /* Health check: if ModeReg lost its value, chip was reset — reinit */
    if (RC522_ReadReg(ModeReg) != 0x3D || RC522_ReadReg(TxControlReg) != 0x83) {
        RC522_HardReset();
    }

    /* Try REQA (7-bit short frame) */
    if (RC522_Transceive(&cmd, 1, back, &backLen, 7)) {
        return 1;
    }
    /* Fallback: WUPA */
    cmd = PICC_WUPA;
    return RC522_Transceive(&cmd, 1, back, &backLen, 7);
}

uint8_t RC522_GetCardUID(uint8_t *uid) {
    uint8_t back[16];
    uint8_t backLen = 0;

    /* 1. REQA */
    uint8_t cmd = PICC_REQA;
    if (!RC522_Transceive(&cmd, 1, back, &backLen, 7)) {
        return 0;  /* REQA failed */
    }

    /* 2. Anticollision */
    uint8_t ac[2] = {PICC_ANTICOLL, 0x20};
    if (!RC522_Transceive(ac, 2, back, &backLen, 0)) {
        return 1;  /* magic: 1=REQA ok, Anticoll failed */
    }

    if (backLen != 40) return 2;  /* should be 5 bytes = 40 bits */

    /* UID = back[0..3], BCC = back[4] */
    uint8_t bcc = 0;
    for (int i = 0; i < 4; i++) { bcc ^= back[i]; uid[i] = back[i]; }
    if (bcc != back[4]) return 3;  /* BCC mismatch */

    /* 3. Select */
    uint8_t sel[9];
    sel[0] = PICC_SELECT;
    sel[1] = 0x70;  /* NVB = 40 valid bits */
    sel[2] = uid[0];
    sel[3] = uid[1];
    sel[4] = uid[2];
    sel[5] = uid[3];
    sel[6] = bcc;
    /* CRC over sel[0..6] */
    RC522_WriteReg(CommandReg, PCD_IDLE);
    RC522_WriteReg(FIFOLevelReg, 0x80);  /* flush */
    for (int i = 0; i < 7; i++) RC522_WriteReg(FIFODataReg, sel[i]);
    RC522_WriteReg(CommandReg, PCD_CALCCRC);
    /* Wait for CRC complete */
    uint16_t cnt = 500;
    while (--cnt && !(RC522_ReadReg(DivIrqReg) & 0x04));
    sel[7] = RC522_ReadReg(CRCResultRegL);
    sel[8] = RC522_ReadReg(CRCResultRegH);

    if (!RC522_Transceive(sel, 9, back, &backLen, 0)) {
        return 5;  /* Select failed */
    }

    return 4;  /* UID length (success) */
}

void RC522_HaltCard(void) {
    uint8_t back[16];
    uint8_t backLen = 0;
    uint8_t halt[4];
    halt[0] = PICC_HALT;
    halt[1] = 0x00;
    /* Calculate CRC */
    RC522_WriteReg(CommandReg, PCD_IDLE);
    RC522_WriteReg(FIFOLevelReg, 0x80);
    RC522_WriteReg(FIFODataReg, halt[0]);
    RC522_WriteReg(FIFODataReg, halt[1]);
    RC522_WriteReg(CommandReg, PCD_CALCCRC);
    uint16_t cnt = 500;
    while (--cnt && !(RC522_ReadReg(DivIrqReg) & 0x04));
    halt[2] = RC522_ReadReg(CRCResultRegL);
    halt[3] = RC522_ReadReg(CRCResultRegH);
    RC522_Transceive(halt, 4, back, &backLen, 0);
}
