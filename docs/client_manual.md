<p><span style="border: 1px solid black;">保密</span></p>

# <center>ImageLabelTS 客户端使用手册</center>

***

## 1. 下载客户端

访问以下地址以下载客户端压缩包：
```
pass
```

## 2. 解压客户端

在桌面新建一个文件夹，并将下载的压缩包解压至该文件夹。
解压后，文件夹应该包含以下内容：
```
ImageLabelTS_sys.client/
    ImageLabelTS.client.exe     # 主程序
    config.json                 # 配置文件
```

**至此，安装完成。**

## 3. 打开命令行窗口

打开您刚刚创建的文件夹，在里面按住`Shift`，然后点击右键，在打开的菜单中选择`在此处打开PowerShell窗口(S)`

## 4. 客户端操作说明

该程序是一个命令行程序，其命令用法如下：
```cmd
.\ImageLabelTS.client.exe [参数]
```
> [!TIP]
> 当您输入`.\ImageL`后按`Tab`就可以自动补全了~

### 4.1 登录

在首次使用时，需要执行登录操作：
```cmd
.\ImageLabelTS.client.exe login <用户名>
```
该命令会要求您输入密码。输入时密码不可见。

在登录成功后，您可以看到一个`.annotator_credential.json`文件，该文件记录了您的登录令牌，以后客户端会自动读取该文件。

若您认为现有令牌不再安全，您可以重新执行登录操作以生成新令牌并使旧令牌失效。

### 4.2 从服务器拉取图片
在登录后，需要从服务器拉取图片：
```cmd
.\ImageLabelTS.client.exe pull
```

该命令会拉取您任务之内的图片和您已经标注的json文件，并保存在workshop文件夹下。

当教师对您执行改派等操作时，也需要重新拉取。

### 4.3 将标注结果推送至服务器

当您完成了标注，需要将标注结果推送至服务器：
```cmd
.\ImageLabelTS.client.exe push
```

该命令会将您本地的workshop文件夹下所有的json文件推送至服务器。

### 4.4 清理工作区
当新一批数据被上传至服务器，或者服务管理员要求清理工作区时，执行以下命令清理工作区：
```cmd
.\ImageLabelTS.client.exe clean
```
执行该命令会清除`workshop`文件夹下的全部文件，请谨慎使用。

### 4.5 更新客户端
当被要求更新客户端时，执行以下命令更新客户端：
```cmd
.\ImageLabelTS.client.exe update
```

### 4.6 诊断和反馈
通过诊断数据收集服务，我们可以获得您的诊断数据，以便帮助我们改进产品。

诊断数据收集服务默认关闭，如需开启，请在`config.json`中将`telemetry_enabled`字段的值设置为`true`。

当技术支持人员或管理员需要查看您的诊断数据时，您可以通过以下命令主动将诊断数据上传至诊断数据收集服务器：
```cmd
.\ImageLabelTS.client.exe upload_log
```
我们尊重您的隐私，您有权利拒绝上传诊断数据。

除此之外，若您开启了诊断数据收集服务，诊断数据将程序发生未捕获的异常时自动上传。

诊断数据包括以下信息：
- 程序使用日志；
- 图片分配信息；
- 执行`pull`与`push`命令所用时间；
- 执行`pull`下载的任务包大小。


以上。
*<div style="text-align: right;">黄浦巍<br>2026年5月16日</div>*