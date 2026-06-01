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
    } else if (strcmp(line, "state") == 0) {
        UART_Printf("STATE: %s\r\n", FSM_StateString(FSM_GetState()));
    } else if (strcmp(line, "help") == 0) {
        UART_Printf("Commands: led R G B, mpu, mpuoff, mpuon, state, help\r\n");
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
  RC522_Init();
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
