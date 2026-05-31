#ifndef MPU6050_HAL_H
#define MPU6050_HAL_H

#include <stdint.h>

#define MPU6050_I2C_ADDR  0xD0  /* AD0=0, shifted for HAL */

typedef enum {
    POSE_STABLE = 0,
    POSE_FALL,
    POSE_SHAKE,
    POSE_PICKUP
} PoseState;

typedef struct {
    float ax, ay, az;   /* acceleration (g) */
    float gx, gy, gz;   /* angular velocity (deg/s) */
    float temp_c;        /* temperature (Celsius) */
} MPU6050_Data;

uint8_t MPU6050_Init(void);
uint8_t MPU6050_ReadData(MPU6050_Data *data);
PoseState MPU6050_DetectPose(const MPU6050_Data *data);
const char* PoseState_String(PoseState s);

#endif
