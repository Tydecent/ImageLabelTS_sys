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
    ImageLabelTS.client.exe
    server.crt
    config.json
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

## 4.1 登录

在首次使用时，需要执行登录操作：
```cmd
.\ImageLabelTS.client.exe login <用户名>
```
用户名就是您自己的中文名字。

在登录成功后，您可以看到一个`.annotator_name`文件，该文件记录了您的用户名，以后客户端会自动读取该文件。

## 4.2 从服务器拉取图片
在登录后，需要从服务器拉取图片：
```cmd
.\ImageLabelTS.client.exe pull
```

该命令会拉取您任务之内的图片和您已经标注的json文件，并保存在workshop文件夹下。

当教师对您执行改派等操作时，也需要重新拉取。

## 4.3 将标注结果推送至服务器

当您完成了标注，需要将标注结果推送至服务器：
```cmd
.\ImageLabelTS.client.exe push
```

该命令会将您本地的workshop文件夹下所有的json文件推送至服务器。

## 4.4 清理工作区
当新一批数据被上传至服务器，或者服务管理员要求清理工作区时，执行以下命令清理工作区：
```cmd
.\ImageLabelTS.client.exe clean
```
执行该命令会清除`workshop`文件夹下的全部文件，请谨慎使用。

## 4.5 更新客户端
当被要求更新客户端时，执行以下命令更新客户端：
```cmd
.\ImageLabelTS.client.exe update
```

## 4.6 遥测服务（用户体验改进计划）
通过遥测服务，我们可以获得您的遥测数据，以便我们改进产品。

遥测服务默认关闭，如需开启，请在`config.json`中将`telemetry_enabled`字段的值设置为`true`。

当技术支持人员或管理员需要查看您的遥测数据时，您可以通过以下命令主动将遥测数据上传至遥测服务器：
```cmd
.\ImageLabelTS.client.exe upload_log
```
我们尊重您的隐私，您有权利拒绝上传遥测数据。

除此之外，若您开启了遥测服务，遥测数据将程序发生未捕获的异常时自动上传。

遥测数据包括以下信息：
- 程序使用日志；
- 图片分配信息；
- 执行`pull`与`push`命令所用时间；
- 执行`pull`下载的任务包大小。


以上。
*<div style="text-align: right;">黄浦巍<br>2026年5月14日</div>*