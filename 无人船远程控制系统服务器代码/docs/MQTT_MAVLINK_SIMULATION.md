# MQTT 与 MAVLink 无硬件联调

## 当前边界

- 电脑串口助手不能直接打开香橙派的串口：4G/NAT 下需要把串口字节流封装后经 MQTT 转发。
- `onboard/services/mqtt_mavlink_tunnel.py` 两端使用同一脚本；香橙派以 `boat` 角色连接 Pixhawk UART，电脑以 `desktop` 角色连接虚拟串口对的一端。MAVLink 二进制流按原字节透传。
- `tools/ardurover_mavlink_sim.py` 用 pymavlink 在电脑端模拟 ArduRover，可发送心跳并响应解锁、MANUAL/AUTO/RTL、任务上传协议。它连接虚拟串口对另一端，可代替暂时不在手边的飞控。
- 电脑串口助手与 pymavlink 模拟器只能有一个程序同时占用虚拟串口对的同一端；使用串口助手时，需手动发送合法 MAVLink 帧，普通 ASCII 文本不是 MAVLink。

## 主题和方向

| 数据流 | MQTT 主题 | QoS | 用途 |
|---|---|---:|---|
| 香橙派 → 云端/电脑 | `usv/{boat_id}/mavlink/up` | 0 | 心跳、遥测、ACK |
| 云端/电脑 → 香橙派 | `usv/{boat_id}/mavlink/down` | 1 | MAVLink 控制/任务帧 |

主题载荷是 JSON envelope：`sid`（发送端会话）、`seq`（分片序号）、`data`（base64 原始 MAVLink 字节）。QoS 1 下用会话序号抑制重投造成的重复串口字节。生产环境应按船号配置 Broker 用户/ACL，只允许该船读自己的 `down`、写自己的 `up`。

## 电脑端仿真步骤

1. 安装并配置虚拟空串口对（例如 COMx↔COMy），确认串口助手和 Python 端分别打开一端。当前电脑尚未确认已安装串口助手或虚拟串口驱动。
2. 安装 Python 依赖：`python -m pip install paho-mqtt pyserial pymavlink`。
3. 电脑桥接端设置 `MQTT_HOST`、`MQTT_PORT`、`MQTT_USERNAME`、`MQTT_PASSWORD`，TLS Broker 同时设置 `MQTT_CA_CERT`；启动：

   ```powershell
   python .\onboard\services\mqtt_mavlink_tunnel.py --role desktop --boat-id boat_1 --serial COMy --baud 57600
   ```

4. 在电脑另一虚拟串口端启动 ArduRover 仿真器：

   ```powershell
   python .\tools\ardurover_mavlink_sim.py --device COMx --baud 57600
   ```

   串口助手可替代模拟器进行手动发收；若要自动验证 COMMAND_ACK 和任务协议，使用 pymavlink 模拟器。

## 香橙派端

香橙派就位并确认 UART 名称/电平/波特率后，安装 `paho-mqtt`、`pyserial`、`pymavlink`，配置同一 Broker 凭据和 CA 证书，再启动：

```sh
python3 /opt/usv/services/mqtt_mavlink_tunnel.py --role boat --boat-id boat_1 --serial /dev/ttyS1 --baud 57600
```

应先做只读心跳/遥测验证；确认串口和飞控映射正确、拆桨/固定船体后，才测试解锁和模式等指令。AUTO/RTL 必须有可信 GPS/Home 条件。

作为 systemd 常驻服务时，将脚本放到 `/opt/usv/services/`，安装 `onboard/systemd/mqtt-mavlink-tunnel.service`，创建 root-only `/etc/usv-mqtt.env`：

```ini
MQTT_HOST=YOUR_SERVER_IP
MQTT_PORT=8883
MQTT_USERNAME=boat_1
MQTT_PASSWORD=替换为独立强密码
MQTT_CA_CERT=/opt/usv/config/ca.crt
USV_BOAT_ID=boat_1
USV_SERIAL=/dev/ttyS1
USV_BAUD=57600
```

配置好后再 `systemctl enable --now mqtt-mavlink-tunnel`。密钥文件权限应限 root 可读；不要把真实密码提交到代码库。

## 云端部署前置条件

本机 Mosquitto 已完成一条 retained MQTT 测试消息的发布、订阅和清理；这仅证明本机 Broker 可用。当前 `YOUR_SERVER_IP:8883` 从电脑不可达。代码库现已加入需显式启用的 TLS Broker profile，匿名访问关闭、按用户名隔离主题。云端部署前先在 `cloud/mqtt/certs/` 放入 CA 和服务端证书/密钥，在 `cloud/mqtt/config/passwords` 建立凭据文件。首次测试可在 Linux 云服务器生成自签名证书（客户端需信任 `server.crt`；生产环境建议使用受控 CA）：

```sh
mkdir -p cloud/mqtt/certs
openssl req -x509 -nodes -newkey rsa:3072 -sha256 -days 365 \
  -keyout cloud/mqtt/certs/server.key -out cloud/mqtt/certs/server.crt \
  -subj "/CN=YOUR_SERVER_IP" -addext "subjectAltName=IP:YOUR_SERVER_IP"
cp cloud/mqtt/certs/server.crt cloud/mqtt/certs/ca.crt
chmod 600 cloud/mqtt/certs/server.key
mosquitto_passwd -c cloud/mqtt/config/passwords boat_1
chown 1883:1883 cloud/mqtt/certs/server.key cloud/mqtt/config/passwords
```

然后运行：

```sh
cd cloud
docker compose --profile mqtt up -d mqtt-broker
```

证书必须包含公网 IP `YOUR_SERVER_IP` 的 IP SAN；`passwords` 可用 `mosquitto_passwd -c cloud/mqtt/config/passwords boat_1` 创建，随后按船号创建账号。不要把匿名明文 1883 暴露到公网。还需在腾讯云安全组和物联卡白名单放行 TCP 8883。完成后用相同脚本从电脑验证 `up/down` 双向，再切到香橙派 4G 实测。

## ArduRover MAVLink 约定

MANUAL=0、AUTO=10、RTL=11；解锁/上锁使用 `MAV_CMD_COMPONENT_ARM_DISARM`，并等待 `COMMAND_ACK`。航点上传应遵循 Mission Protocol 的 request/response 顺序（`MISSION_COUNT` → `MISSION_REQUEST_INT` ↔ `MISSION_ITEM_INT` → `MISSION_ACK`），不要像现有云端 `BoatConnection._upload_mission()` 那样不等飞控请求就连续推送航点。
