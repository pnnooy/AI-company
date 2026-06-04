/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "i2c.h"
#include "spi.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"
#include "fsmc.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "ili9341_fsmc.h"
#include "rgb_led.h"
#include "uart_comm.h"
#include "touch_sensor.h"
#include "mpu6050_hal.h"
#include "soft_i2c.h"
#include "rc522_spi.h"
#include "expression_engine.h"
#include "main_fsm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static void TextCmdHandler(const char *line) {
    if (strncmp(line, "led ", 4) == 0) {
        int r, g, b;
        if (sscanf(line, "led %d %d %d", &r, &g, &b) == 3) {
            RGB_StopEffect();
            RGB_SetColor((uint8_t)r, (uint8_t)g, (uint8_t)b);
            UART_Printf("OK: LED=(%d,%d,%d)\r\n", r, g, b);
        }
    } else if (strcmp(line, "mpu") == 0) {
        MPU6050_Data d;
        if (MPU6050_ReadData(&d)) {
            UART_Printf("ACC: X=%.2f Y=%.2f Z=%.2f g\r\n", d.ax, d.ay, d.az);
            UART_Printf("GYRO: X=%.1f Y=%.1f Z=%.1f deg/s\r\n", d.gx, d.gy, d.gz);
            UART_Printf("POSE: %s\r\n", PoseState_String(MPU6050_DetectPose(&d)));
        } else {
            UART_Printf("MPU6050 not found (SW I2C PA11/PA12)\r\n");
        }
    } else if (strncmp(line, "emo ", 4) == 0) {
        const char *names[] = {"normal","happy","focus","angry","sleep","surprise","sad","love"};
        for (int ei = 0; ei < 8; ei++) {
            if (strstr(line + 4, names[ei])) {
                Expression_Set((Expression)ei);
                UART_Printf("OK: emo=%s\r\n", names[ei]);
                break;
            }
        }
    } else if (strncmp(line, "lcd ", 4) == 0) {
        int r, g, b;
        if (sscanf(line + 4, "%d %d %d", &r, &g, &b) == 3) {
            uint16_t c = ((r>>3)<<11) | ((g>>2)<<5) | (b>>3);
            ILI9341_FillScreen(c);
            UART_Printf("LCD fill: RGB(%d,%d,%d)\r\n", r, g, b);
        }
    } else if (strcmp(line, "calib") == 0) {
        ILI9341_DrawTestPattern();
        UART_Printf("Test pattern: 8 colors + 16-bit walk\r\n");
        UART_Printf("Top: BLK RED GRN BLU YEL CYN MAG WHT\r\n");
        UART_Printf("Bot: 4x4 bit walk (bit0-15, left-right, top-down)\r\n");
        FSM_SetPoseEnable(0);
        UART_Printf("MPU polling OFF\r\n");
    } else if (strcmp(line, "mpuon") == 0) {
        FSM_SetPoseEnable(1);
        UART_Printf("MPU polling ON\r\n");
    } else if (strcmp(line, "nfcoff") == 0) {
        FSM_SetNfcEnable(0);
        UART_Printf("NFC polling OFF (manual test mode)\r\n");
    } else if (strcmp(line, "nfcon") == 0) {
        FSM_SetNfcEnable(1);
        UART_Printf("NFC polling ON\r\n");
    } else if (strcmp(line, "state") == 0) {
        UART_Printf("STATE: %s\r\n", FSM_StateString(FSM_GetState()));
    } else if (strcmp(line, "nfc") == 0) {
        uint8_t uid[10];
        UART_Printf("=== NFC Diagnostic ===\r\n");

        /* Step 1: Check register health */
        uint8_t mode = RC522_ReadReg(0x11);  /* ModeReg */
        uint8_t txctl = RC522_ReadReg(0x14); /* TxControlReg */
        UART_Printf("1. Chip state: Mode=0x%02X TxCtl=0x%02X ", mode, txctl);
        if (mode == 0x3D && txctl == 0x83) {
            UART_Printf("OK\r\n");
        } else {
            UART_Printf("BAD (expect 0x3D/0x83)\r\n");
        }

        /* Step 2: Check card presence */
        UART_Printf("2. CheckCard: ");
        if (RC522_CheckCard()) {
            UART_Printf("DETECTED\r\n");

            /* Step 3: Try GetCardUID */
            UART_Printf("3. GetCardUID: ");
            uint8_t len = RC522_GetCardUID(uid);
            if (len == 4) {
                UART_Printf("SUCCESS - UID: %02X%02X%02X%02X\r\n",
                            uid[0], uid[1], uid[2], uid[3]);
            } else if (len == 0) {
                UART_Printf("FAIL at REQA\r\n");
                /* Show RF config */
                uint8_t rfcfg = RC522_ReadReg(0x26);
                uint8_t rxsel = RC522_ReadReg(0x17);
                UART_Printf("   RFCfg=0x%02X RxSel=0x%02X (try 'nfcboost')\r\n", rfcfg, rxsel);
            } else if (len == 1) {
                UART_Printf("FAIL at Anticollision\r\n");
            } else if (len == 2) {
                UART_Printf("FAIL: wrong length\r\n");
            } else if (len == 3) {
                UART_Printf("FAIL: BCC error\r\n");
            } else {
                UART_Printf("FAIL at Select\r\n");
            }
        } else {
            UART_Printf("NO CARD (move closer, < 3cm)\r\n");
        }
    } else if (strcmp(line, "nfcreset") == 0) {
        /* Hard reset RC522: toggling RST pin + soft reset */
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);
        HAL_Delay(10);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_SET);
        HAL_Delay(50);
        /* Soft reset */
        RC522_WriteReg(0x01, 0x0F);  /* CommandReg = SoftReset */
        HAL_Delay(50);
        uint8_t v = RC522_ReadReg(0x37);
        UART_Printf("RC522 after reset: Ver=0x%02X  CommReg=0x%02X  ComIrq=0x%02X\r\n",
            v, RC522_ReadReg(0x01), RC522_ReadReg(0x04));
    } else if (strcmp(line, "nfcdbg") == 0) {
        /* Warm up SPI link — first byte after idle can glitch */
        RC522_Wakeup();
        /* First, check if SPI is alive by reading version */
        uint8_t v = RC522_ReadReg(0x37);
        UART_Printf("RC522 Ver: 0x%02X\r\n", v);
        /* Dump key RC522 registers */
        UART_Printf("  ComIrq=0x%02X  ComIEn=0x%02X  DivIrq=0x%02X\r\n",
            RC522_ReadReg(0x04), RC522_ReadReg(0x02), RC522_ReadReg(0x05));
        UART_Printf("  Error=0x%02X   FIFOLevel=0x%02X  Coll=0x%02X\r\n",
            RC522_ReadReg(0x06), RC522_ReadReg(0x0A), RC522_ReadReg(0x0E));
        UART_Printf("  BitFraming=0x%02X  TxControl=0x%02X  Mode=0x%02X\r\n",
            RC522_ReadReg(0x0D), RC522_ReadReg(0x14), RC522_ReadReg(0x11));
        UART_Printf("  CommReg=0x%02X  Status2=0x%02X\r\n",
            RC522_ReadReg(0x01), RC522_ReadReg(0x08));
    } else if (strcmp(line, "nfcboost") == 0) {
        /* Boost RF power for weak cards/antennas */
        UART_Printf("Boosting RF power...\r\n");
        RC522_WriteReg(0x26, 0x4F);  /* RFCfgReg: 25dB (was 18dB) */
        UART_Printf("RFCfg=0x%02X (was 0x48)\r\n", RC522_ReadReg(0x26));
        UART_Printf("Try 'nfc' again. If chip resets, power supply too weak.\r\n");
    } else if (strcmp(line, "nfclow") == 0) {
        /* Lower RF power to prevent reset on weak power */
        UART_Printf("Lowering RF power...\r\n");
        RC522_WriteReg(0x26, 0x40);  /* RFCfgReg: 13dB (lowest stable) */
        UART_Printf("RFCfg=0x%02X (was 0x48)\r\n", RC522_ReadReg(0x26));
        UART_Printf("Try 'nfc' again. Should be more stable.\r\n");
    } else if (strcmp(line, "nfcraw") == 0) {
        /* Raw RF test - check if we can receive ATQA */
        UART_Printf("=== Raw REQA Test ===\r\n");
        uint8_t cmd = 0x26;  /* REQA */
        uint8_t back[16];
        uint8_t backLen = 0;

        /* Manual transceive with diagnostics */
        RC522_WriteReg(0x0D, 0x07);  /* BitFraming: 7 bits in last byte */
        RC522_WriteReg(0x01, 0x00);  /* Idle */
        RC522_WriteReg(0x04, 0x7F);  /* Clear IRQ */
        RC522_WriteReg(0x0A, 0x80);  /* Flush FIFO */
        RC522_WriteReg(0x09, cmd);   /* Write REQA to FIFO */
        RC522_WriteReg(0x01, 0x0C);  /* Transceive */
        RC522_WriteReg(0x0D, 0x87);  /* StartSend */

        HAL_Delay(10);  /* Wait for response */

        uint8_t irq = RC522_ReadReg(0x04);    /* ComIrqReg */
        uint8_t err = RC522_ReadReg(0x06);    /* ErrorReg */
        uint8_t fifo = RC522_ReadReg(0x0A);   /* FIFOLevel */

        UART_Printf("IRQ=0x%02X Err=0x%02X FIFO=%d bytes\r\n", irq, err, fifo);

        if (fifo > 0) {
            UART_Printf("RX Data: ");
            for (int i = 0; i < fifo && i < 16; i++) {
                UART_Printf("%02X ", RC522_ReadReg(0x09));
            }
            UART_Printf("\r\n");
        }

        RC522_WriteReg(0x01, 0x00);  /* Back to idle */
    } else if (strcmp(line, "help") == 0) {
        UART_Printf("Commands: led R G B, mpu, mpuon, mpuoff, nfc, nfcoff, nfcon, nfcboost, nfclow, nfcraw, nfcdbg, nfcreset, state, help\r\n");
    } else if (strlen(line) > 0) {
        UART_Printf("? '%s'\r\n", line);
    }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */
  __HAL_AFIO_REMAP_TIM3_PARTIAL();
  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_FSMC_Init();
  MX_I2C1_Init();
  MX_SPI1_Init();
  MX_USART1_UART_Init();
  MX_TIM3_Init();
  /* USER CODE BEGIN 2 */
  ILI9341_Init();
  RGB_Init();
  UART_Init();
  UART_RegisterTextCallback(TextCmdHandler);
  Touch_Init();
  MPU6050_Init();
  if (RC522_Init()) {
    uint8_t ver = RC522_GetVersion();
    UART_Printf("RC522 OK: SPI 2MHz, Ver=0x%02X\r\n", ver);
  } else {
    UART_Printf("RC522 FAIL: SPI unreliable or chip absent\r\n");
  }
  FSM_Init();

  /* Boot blink: 3 quick blue flashes to confirm init complete */
  for (int i = 0; i < 3; i++) {
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_4, 255);
    HAL_Delay(100);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_4, 0);
    HAL_Delay(100);
  }

  UART_Printf("Desktop Assistant Ready\r\n");
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    FSM_Tick();
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == GPIO_PIN_4) {
        Touch_IRQ_Left();
    } else if (GPIO_Pin == GPIO_PIN_5) {
        Touch_IRQ_Right();
    }
}

#ifdef __GNUC__
int __io_putchar(int ch)
#else
int fputc(int ch, FILE *f)
#endif
{
    HAL_UART_Transmit(&huart1, (uint8_t *)&ch, 1, 10);
    return ch;
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
