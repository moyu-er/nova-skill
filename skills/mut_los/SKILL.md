---
name: mut-los-alarm-troubleshooting
description: >-
  XXX 网元 MUT_LOS 告警排障流程。当用户输入网元告警排障请求（如"XXX网元MUT_LOS告警如何处理"、
  "帮我排查XXX网元的光中断告警"）时触发。共 24 步，涵盖告警查询、模式识别、
  站内/站间故障判断、光功率查询、修复建议输出。
---

# MUT_LOS 告警排障 Skill

## Overview

本 Skill 处理网元 MUT_LOS（光信号丢失）告警的端到端排障流程。

**输入**：用户提供的告警描述，包含网元名、单板、端口、告警类型。  
**输出**：故障段定位、光功率数据、影响业务列表、修复建议。

**流程主干**：
1. 提取参数 → 查询告警 → 判断是否已清除
2. 若持续：识别告警模式 → 判断是否频闪
3. 若非频闪：查询故障流水号 → 查询故障段 → 判断站内/站间
4. 站间：查监控光功率 → 判断是否中断 → 输出故障段和建议
5. 站内：查宿端口光功率 → 输出故障段和建议

---

## API 字段说明

> 以下为本 Skill 涉及的所有 API，供构建 tool_list 使用。

```yaml
apis:
  - id: queryAlarmList
    description: 查询当前和历史告警列表
    method: POST
    path: /api/alarm/queryAlarmList
    request_fields:
      - name: neName        # 网元名称
      - name: boardName     # 单板名称
      - name: portName      # 端口名称
      - name: alarmType     # 告警类型，如 MUT_LOS
      - name: startTime     # 查询起始时间（历史告警用）
      - name: endTime       # 查询结束时间（历史告警用）
    response_fields:
      - name: alarmId       # 告警 ID
      - name: alarmStatus   # 告警状态：ACTIVE / CLEARED
      - name: eventId       # 关联事件 ID（后续步骤使用）
      - name: occurTime     # 告警发生时间
      - name: clearTime     # 告警清除时间（CLEARED 时有值）

  - id: queryAffectedService
    description: 查询告警影响的业务
    method: POST
    path: /api/service/queryAffectedService
    request_fields:
      - name: alarmId       # 告警 ID，来自 queryAlarmList 响应
    response_fields:
      - name: serviceList   # 受影响业务列表
      - name: serviceId
      - name: serviceName
      - name: serviceType

  - id: queryFaultSeqNo
    description: 根据 eventId 查询故障流水号
    method: GET
    path: /api/fault/queryFaultSeqNo
    request_fields:
      - name: eventId       # 来自 queryAlarmList 响应的 eventId
    response_fields:
      - name: faultSeqNo    # 故障流水号（后续步骤使用）

  - id: queryAlarmGroupList
    description: 根据故障流水号查询告警组中的告警列表
    method: GET
    path: /api/fault/queryAlarmGroupList
    request_fields:
      - name: faultSeqNo    # 来自 queryFaultSeqNo 响应
    response_fields:
      - name: alarmCount    # 关联告警总数
      - name: alarmList     # 告警列表
      - name: portModn      # 宿端口 modn（站内故障 Step 22 使用）

  - id: queryFaultSegment
    description: 根据故障流水号查询故障段
    method: GET
    path: /api/fault/queryFaultSegment
    request_fields:
      - name: faultSeqNo    # 来自 queryFaultSeqNo 响应
    response_fields:
      - name: segmentType   # 故障段类型：INTRA_SITE（站内）/ INTER_SITE（站间）
      - name: srcNode       # 故障段源端节点
      - name: dstNode       # 故障段宿端节点
      - name: srcPort       # 源端口
      - name: dstPort       # 宿端口
      - name: dstPortModn   # 宿端口 modn

  - id: queryMonitorPort
    description: 查询路径对应的监控板端口
    method: POST
    path: /api/port/queryMonitorPort
    request_fields:
      - name: faultSeqNo
      - name: srcNode
      - name: dstNode
    response_fields:
      - name: monitorPortId
      - name: monitorPortName
      - name: boardName

  - id: queryPortOpticalPower
    description: 查询端口当前光功率（监控光功率和普通端口光功率复用此接口）
    method: GET
    path: /api/optical/queryPortOpticalPower
    request_fields:
      - name: neName
      - name: boardName
      - name: portName
    response_fields:
      - name: rxPower       # 接收光功率（dBm）
      - name: txPower       # 发送光功率（dBm）
      - name: threshold     # 光功率阈值
      - name: status        # 正常 / 异常

  - id: queryOAOpticalPower
    description: 查询光纤延伸至两端 OA 的输入/输出光功率
    method: POST
    path: /api/optical/queryOAOpticalPower
    request_fields:
      - name: faultSeqNo
      - name: monitorPortId
    response_fields:
      - name: oaInputPower    # OA 输入光功率（dBm）
      - name: oaOutputPower   # OA 输出光功率（dBm）
      - name: interruptPoint  # 中断点位置（监控光中断时有值）
      - name: isInterrupted   # 布尔值：监控光是否中断

  - id: queryPortHistoryPower
    description: 查询端口历史光功率
    method: POST
    path: /api/optical/queryPortHistoryPower
    request_fields:
      - name: neName
      - name: portModn        # 宿端口 modn，来自 queryAlarmGroupList 或 queryFaultSegment
      - name: startTime
      - name: endTime
    response_fields:
      - name: historyPowerList
      - name: timestamp
      - name: rxPower
      - name: txPower
```

---

## Steps

### Step 1: 关键参数提取

**类型**：LLM 推理  
**输入**：用户原始输入文本  
**操作**：从用户输入中提取以下结构化参数，后续所有步骤复用：

```
neName     = <网元名称>
boardName  = <单板名称，若未提及则为 null>
portName   = <端口名称，若未提及则为 null>
alarmType  = "MUT_LOS"
```

若用户输入缺少网元名称，**停止执行并回复**：
> "请提供需要排障的网元名称。"

---

### Step 2: 查询告警状态

**类型**：API 调用  
**调用**：`queryAlarmList`  
**请求参数**：
```json
{
  "neName": "<Step 1 提取的 neName>",
  "boardName": "<Step 1 提取的 boardName>",
  "portName": "<Step 1 提取的 portName>",
  "alarmType": "MUT_LOS"
}
```
**将响应完整保存为** `alarmList`，后续步骤引用。

---

### Step 3: [判断] if 告警状态已清除

**类型**：LLM 判断  
**判断依据**：检查 `alarmList` 中所有告警的 `alarmStatus` 字段：
- 若**全部为 `CLEARED`** → **是**：向用户输出以下内容，然后结束：
  > "告警已清除。告警 ID：`<alarmId>`，清除时间：`<clearTime>`。当前网元运行正常，无需进一步处理。"
- 若**存在 `ACTIVE`** → **否**：继续执行 Step 4

---

### Step 4: 基于告警列表识别告警模式

**类型**：LLM 推理  
**输入**：`alarmList`  
**操作**：分析告警的发生/清除时间规律，判断告警模式：
- **频闪**：告警在短时间内多次出现和清除（例如 1 小时内超过 3 次 ACTIVE-CLEARED 循环）
- **持续**：告警持续处于 ACTIVE 状态

将判断结果保存为 `alarmPattern`（值为 `"flapping"` 或 `"persistent"`）。

---

### Step 5: [判断] if 告警状态频闪

**类型**：LLM 判断  
**判断依据**：`alarmPattern == "flapping"`
- 若**是** → 跳转到 Step 6（频闪处理分支）
- 若**否** → 跳转到 Step 10（持续告警处理主流程）

---

### Step 6: 频闪告警提示

**类型**：输出  
**输出内容**（直接向用户展示）：

> **⚠️ 检测到频闪告警**
>
> 网元 `<neName>` 的 MUT_LOS 告警处于频闪状态（短时间内反复出现和清除）。
>
> **可能原因**：
> - 光纤连接松动或接触不良
> - 对端设备发送光功率不稳定
> - 光模块老化
>
> **建议操作**：
> 1. 检查该端口的光纤连接是否紧固
> 2. 查看对端设备的发送光功率历史趋势
> 3. 若频繁发生，建议更换光模块

完成后继续执行 Step 7（输出故障段和影响业务汇总）。

---

### Step 7: 输出故障段、光功率、修复建议（汇总出口）

**类型**：输出  
**说明**：这是所有分支路径的最终汇总输出点，Step 20、21、24 执行完毕后均跳转至此。  
**输出内容**（整合当前已收集的所有信息）：

```
## 排障结论

**网元**：<neName>
**告警类型**：MUT_LOS
**故障段**：<来自 Step 20/21/24 的故障段描述>
**光功率**：<来自 Step 20/21/24 的光功率数据>
**关联告警数**：<来自 Step 12 的统计结果，若有>
**影响业务**：<来自 Step 8 的业务列表，若有>

**修复建议**：
<来自 Step 20/21/24 的具体建议>
```

继续执行 Step 8。

---

### Step 8: 查询影响业务

**类型**：API 调用  
**调用**：`queryAffectedService`  
**请求参数**：
```json
{
  "alarmId": "<alarmList 中第一条 ACTIVE 告警的 alarmId>"
}
```
**将响应保存为** `affectedServices`，并追加输出至 Step 7 的结论中：

> **影响业务**：共 `<serviceList.length>` 条  
> `<serviceId>` - `<serviceName>`（`<serviceType>`）

---

### Step 9: 流程结束

**类型**：结束  
完成全部排障输出，等待用户进一步指令。

---

### Step 10: 根据 event 查询故障流水号

**类型**：API 调用  
**调用**：`queryFaultSeqNo`  
**请求参数**：
```json
{
  "eventId": "<alarmList 中第一条 ACTIVE 告警的 eventId>"
}
```
**将响应中的 `faultSeqNo` 保存**，后续 Step 11、13、16 使用。

---

### Step 11: 根据故障流水号查询告警组中告警列表

**类型**：API 调用  
**调用**：`queryAlarmGroupList`  
**请求参数**：
```json
{
  "faultSeqNo": "<Step 10 获取的 faultSeqNo>"
}
```
**将响应完整保存为** `alarmGroupResult`。

---

### Step 12: 统计关联告警个数

**类型**：LLM 推理  
**输入**：`alarmGroupResult`  
**操作**：统计 `alarmGroupResult.alarmList` 的长度，记录为 `relatedAlarmCount`。  
**暂不输出**，在 Step 7 汇总时一并展示。

---

### Step 13: 根据故障流水号查询故障段

**类型**：API 调用  
**调用**：`queryFaultSegment`  
**请求参数**：
```json
{
  "faultSeqNo": "<Step 10 获取的 faultSeqNo>"
}
```
**将响应完整保存为** `faultSegment`。

---

### Step 14: 确认站内还是站间故障

**类型**：LLM 推理  
**输入**：`faultSegment`  
**操作**：读取 `faultSegment.segmentType`：
- `"INTRA_SITE"` → 站内故障
- `"INTER_SITE"` → 站间故障

将结果保存为 `faultScopeType`。

---

### Step 15: [判断] 站内故障

**类型**：LLM 判断  
**判断依据**：`faultScopeType == "INTRA_SITE"`
- 若**否**（站间） → 跳转到 Step 16（站间处理分支）
- 若**是**（站内） → 跳转到 Step 22（站内处理分支）

---

### Step 16: 查询路径对应监控板端口

**类型**：API 调用  
**调用**：`queryMonitorPort`  
**请求参数**：
```json
{
  "faultSeqNo": "<faultSeqNo>",
  "srcNode": "<faultSegment.srcNode>",
  "dstNode": "<faultSegment.dstNode>"
}
```
**将响应保存为** `monitorPort`。

---

### Step 17: 查询监控光功率

**类型**：API 调用  
**调用**：`queryPortOpticalPower`  
**请求参数**：
```json
{
  "neName": "<neName>",
  "boardName": "<monitorPort.boardName>",
  "portName": "<monitorPort.monitorPortName>"
}
```
**将响应保存为** `monitorOpticalPower`。

---

### Step 18: 查询两端 OA 光功率

**类型**：API 调用  
**调用**：`queryOAOpticalPower`  
**请求参数**：
```json
{
  "faultSeqNo": "<faultSeqNo>",
  "monitorPortId": "<monitorPort.monitorPortId>"
}
```
**将响应保存为** `oaPowerResult`。

---

### Step 19: [判断] 监控光中断

**类型**：LLM 判断  
**判断依据**：`oaPowerResult.isInterrupted == true`
- 若**是** → 跳转到 Step 20（中断点定位）
- 若**否** → 跳转到 Step 21（OA前尾纤问题）

---

### Step 20: 输出站间故障段、中断点、修复建议

**类型**：输出  
**将以下内容保存为变量**供 Step 7 使用：

```
故障段   = "<faultSegment.srcNode> → <faultSegment.dstNode>"
中断点   = "<oaPowerResult.interruptPoint>"
光功率   = "监控光 RX: <monitorOpticalPower.rxPower> dBm | OA输入: <oaPowerResult.oaInputPower> dBm"
修复建议 = "站间光纤在 <oaPowerResult.interruptPoint> 处发生中断，建议：
           1. 联系线路运维人员对该段光纤进行 OTDR 测试
           2. 检查 <interruptPoint> 附近的光纤接头、熔接点
           3. 确认是否存在施工挖断或物理损坏"
```

完成后跳转回 Step 7 进行汇总输出。

---

### Step 21: 输出故障段（OA 前站内尾纤）

**类型**：输出  
**将以下内容保存为变量**供 Step 7 使用：

```
故障段   = "OA 前站内尾纤（<faultSegment.srcNode> 侧）"
光功率   = "监控光 RX: <monitorOpticalPower.rxPower> dBm | OA输入: <oaPowerResult.oaInputPower> dBm（未中断但功率异常）"
修复建议 = "监控光未中断但 OA 输入光功率偏低，故障位于 OA 前站内尾纤段，建议：
           1. 检查 <faultSegment.srcNode> 机房内 OA 前的尾纤连接
           2. 清洁尾纤端面
           3. 测量尾纤衰减值"
```

完成后跳转回 Step 7 进行汇总输出。

---

### Step 22: 提取故障段宿端口 modn

**类型**：LLM 推理  
**输入**：`faultSegment`（来自 Step 13 响应，已包含 `dstPortModn` 字段）  
**操作**：读取 `faultSegment.dstPortModn`，保存为 `dstPortModn`。

---

### Step 23: 查询宿端口当前光功率和历史光功率

**类型**：API 调用（并行执行两个接口）

**调用 1**：`queryPortOpticalPower`  
```json
{
  "neName": "<neName>",
  "boardName": "<faultSegment.dstPort 所在单板>",
  "portName": "<faultSegment.dstPort>"
}
```
**保存响应为** `dstPortCurrentPower`。

**调用 2**：`queryPortHistoryPower`  
```json
{
  "neName": "<neName>",
  "portModn": "<dstPortModn>",
  "startTime": "<告警发生时间前 24 小时>",
  "endTime": "<当前时间>"
}
```
**保存响应为** `dstPortHistoryPower`。

---

### Step 24: 输出站内故障段、光功率信息、修复建议

**类型**：输出  
**将以下内容保存为变量**供 Step 7 使用：

```
故障段   = "站内故障：<faultSegment.srcNode> → <faultSegment.dstNode>，宿端口 <faultSegment.dstPort>"
光功率   = "当前 RX: <dstPortCurrentPower.rxPower> dBm（阈值: <dstPortCurrentPower.threshold> dBm）
           历史趋势: <dstPortHistoryPower 最近24小时最低值> dBm ~ <最高值> dBm"
修复建议 = "宿端口接收光功率 <dstPortCurrentPower.rxPower> dBm，低于阈值，站内故障，建议：
           1. 检查 <faultSegment.dstNode> 的 <faultSegment.dstPort> 端口尾纤连接
           2. 检查对应光模块收发状态
           3. 若历史光功率突降，排查光纤是否受到挤压或弯折"
```

完成后跳转回 Step 7 进行汇总输出。
