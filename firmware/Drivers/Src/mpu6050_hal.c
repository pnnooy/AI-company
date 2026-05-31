#include "mpu6050_hal.h"
#include "soft_i2c.h"
#include <math.h>

/*
 * MPU6050 driver using software I2C (PA11=SCL, PA12=SDA).
 * Hardware I2C1 (PB6/PB7) conflicts with FSMC NADV.
 */

#define MPU_REG_WHO_AM_I    0x75
#define MPU_REG_PWR_MGMT1   0x6B
#define MPU_REG_ACCEL_XOUT  0x3B
#define MPU_REG_GYRO_XOUT   0x43
#define MPU_REG_ACCEL_CONFIG 0x1C
#define MPU_REG_GYRO_CONFIG  0x1B
#define MPU_REG_SMPLRT_DIV   0x19

#define ACCEL_SCALE  16384.0f  /* ±2g */
#define GYRO_SCALE   131.0f    /* ±250 deg/s */

static int mpu_ready;

uint8_t MPU6050_Init(void) {
    mpu_ready = 0;

    SoftI2C_Init();

    /* Read WHO_AM_I */
    uint8_t whoami;
    if (!SoftI2C_ReadReg(MPU6050_ADDR, MPU_REG_WHO_AM_I, &whoami, 1)) return 0;
    if (whoami != 0x68) return 0;

    /* Wake up */
    SoftI2C_WriteReg(MPU6050_ADDR, MPU_REG_PWR_MGMT1, 0x00);
    HAL_Delay(50);

    /* Sample rate: 1kHz / (1+4) = 200Hz */
    SoftI2C_WriteReg(MPU6050_ADDR, MPU_REG_SMPLRT_DIV, 0x04);

    /* Accelerometer: ±2g */
    SoftI2C_WriteReg(MPU6050_ADDR, MPU_REG_ACCEL_CONFIG, 0x00);

    /* Gyroscope: ±250 deg/s */
    SoftI2C_WriteReg(MPU6050_ADDR, MPU_REG_GYRO_CONFIG, 0x00);

    mpu_ready = 1;
    return 1;
}

uint8_t MPU6050_ReadData(MPU6050_Data *data) {
    if (!mpu_ready || !data) return 0;

    uint8_t raw[14];
    if (!SoftI2C_ReadReg(MPU6050_ADDR, MPU_REG_ACCEL_XOUT, raw, 14)) return 0;

    int16_t ax = (raw[0] << 8) | raw[1];
    int16_t ay = (raw[2] << 8) | raw[3];
    int16_t az = (raw[4] << 8) | raw[5];
    int16_t temp = (raw[6] << 8) | raw[7];
    int16_t gx = (raw[8] << 8) | raw[9];
    int16_t gy = (raw[10] << 8) | raw[11];
    int16_t gz = (raw[12] << 8) | raw[13];

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
    float accel_mag = sqrtf(data->ax * data->ax +
                            data->ay * data->ay +
                            data->az * data->az);
    float gyro_mag = sqrtf(data->gx * data->gx +
                           data->gy * data->gy +
                           data->gz * data->gz);

    if (accel_mag < 0.4f || accel_mag > 2.5f) return POSE_FALL;
    if (gyro_mag > 200.0f) return POSE_SHAKE;
    return POSE_STABLE;
}

const char* PoseState_String(PoseState s) {
    switch (s) {
        case POSE_STABLE: return "STABLE";
        case POSE_FALL:   return "FALL";
        case POSE_SHAKE:  return "SHAKE";
        default:          return "UNKNOWN";
    }
}
