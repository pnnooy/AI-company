#include "mpu6050_hal.h"
#include "stm32f1xx_hal.h"
#include "i2c.h"
#include <math.h>

/* MPU6050 register addresses */
#define MPU_REG_WHO_AM_I    0x75
#define MPU_REG_PWR_MGMT1   0x6B
#define MPU_REG_ACCEL_XOUT  0x3B
#define MPU_REG_GYRO_XOUT   0x43
#define MPU_REG_ACCEL_CONFIG 0x1C
#define MPU_REG_GYRO_CONFIG  0x1B
#define MPU_REG_SMPLRT_DIV   0x19

#define MPU_WHO_AM_I_VALUE   0x68

/* calibration: 1g = 16384 (for ±2g range) */
#define ACCEL_SCALE  16384.0f
/* calibration: 1 deg/s = 131 (for ±250 deg/s range) */
#define GYRO_SCALE   131.0f

static int mpu_ready;

static uint8_t MPU_ReadReg(uint8_t reg, uint8_t *data, uint8_t len) {
    return HAL_I2C_Mem_Read(&hi2c1, MPU6050_I2C_ADDR, reg,
                            I2C_MEMADD_SIZE_8BIT, data, len, 100) == HAL_OK;
}

static uint8_t MPU_WriteReg(uint8_t reg, uint8_t val) {
    return HAL_I2C_Mem_Write(&hi2c1, MPU6050_I2C_ADDR, reg,
                             I2C_MEMADD_SIZE_8BIT, &val, 1, 100) == HAL_OK;
}

uint8_t MPU6050_Init(void) {
    uint8_t whoami;
    mpu_ready = 0;

    if (!MPU_ReadReg(MPU_REG_WHO_AM_I, &whoami, 1)) return 0;
    if (whoami != MPU_WHO_AM_I_VALUE) return 0;

    /* Wake up device (clear sleep bit) */
    MPU_WriteReg(MPU_REG_PWR_MGMT1, 0x00);
    HAL_Delay(100);

    /* Sample rate divider: 1kHz / (1+4) = 200Hz */
    MPU_WriteReg(MPU_REG_SMPLRT_DIV, 0x04);

    /* Accelerometer: ±2g */
    MPU_WriteReg(MPU_REG_ACCEL_CONFIG, 0x00);

    /* Gyroscope: ±250 deg/s */
    MPU_WriteReg(MPU_REG_GYRO_CONFIG, 0x00);

    mpu_ready = 1;
    return 1;
}

uint8_t MPU6050_ReadData(MPU6050_Data *data) {
    if (!mpu_ready || !data) return 0;

    uint8_t raw[14];
    if (!MPU_ReadReg(MPU_REG_ACCEL_XOUT, raw, 14)) return 0;

    /* MPU6050 data is big-endian int16 */
    int16_t ax = (int16_t)((raw[0] << 8) | raw[1]);
    int16_t ay = (int16_t)((raw[2] << 8) | raw[3]);
    int16_t az = (int16_t)((raw[4] << 8) | raw[5]);
    int16_t temp = (int16_t)((raw[6] << 8) | raw[7]);
    int16_t gx = (int16_t)((raw[8] << 8) | raw[9]);
    int16_t gy = (int16_t)((raw[10] << 8) | raw[11]);
    int16_t gz = (int16_t)((raw[12] << 8) | raw[13]);

    data->ax = ax / ACCEL_SCALE;
    data->ay = ay / ACCEL_SCALE;
    data->az = az / ACCEL_SCALE;
    data->gx = gx / GYRO_SCALE;
    data->gy = gy / GYRO_SCALE;
    data->gz = gz / GYRO_SCALE;
    data->temp_c = temp / 340.0f + 36.53f;

    return 1;
}

PoseState MPU6050_DetectPose(const MPU6050_Data *data) {
    /* magnitude of acceleration vector */
    float accel_mag = sqrtf(data->ax * data->ax +
                            data->ay * data->ay +
                            data->az * data->az);

    /* magnitude of angular velocity */
    float gyro_mag = sqrtf(data->gx * data->gx +
                           data->gy * data->gy +
                           data->gz * data->gz);

    /* Fall detection: acceleration deviates significantly from 1g */
    if (accel_mag < 0.4f || accel_mag > 2.5f) return POSE_FALL;

    /* Shake detection: high angular velocity */
    if (gyro_mag > 200.0f) return POSE_SHAKE;

    /* Pickup: significant change in vertical acceleration */
    if (fabsf(data->az - 1.0f) > 0.6f) return POSE_PICKUP;

    return POSE_STABLE;
}

const char* PoseState_String(PoseState s) {
    switch (s) {
        case POSE_STABLE: return "STABLE";
        case POSE_FALL:   return "FALL";
        case POSE_SHAKE:  return "SHAKE";
        case POSE_PICKUP: return "PICKUP";
        default:          return "UNKNOWN";
    }
}
