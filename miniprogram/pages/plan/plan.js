// pages/plan/plan.js
Page({
  data: {
    status: 'success',
    statusText: '规划完成',
    statusDesc: '所有任务已成功执行',
    tasks: [],
    notification: '',
    totalCount: 0,
    successCount: 0,
    pendingCount: 0,
    totalCost: 0,
    timeline: []
  },

  onLoad(options) {
    if (options.id) {
      this.loadPlan(options.id);
    }
  },

  // 加载行程数据
  loadPlan(planId) {
    // 从缓存或 API 获取行程数据
    const planData = wx.getStorageSync(`plan_${planId}`);

    if (planData) {
      this.processPlanData(planData);
    } else {
      // 无真实数据时显示错误，不兜底假数据
      this.setData({
        status: 'error',
        statusText: '行程未找到',
        statusDesc: '该行程数据不存在或已过期，请返回首页重新规划',
        tasks: [],
        timeline: []
      });
    }
  },

  // 处理行程数据
  processPlanData(data) {
    const statusTextMap = {
      'success': '规划完成',
      'partial': '部分完成',
      'error': '执行失败',
      'replan_needed': '重新规划中'
    };

    const statusDescMap = {
      'success': '所有任务已成功执行',
      'partial': '部分任务执行失败，已启用备选方案',
      'error': '任务执行遇到问题',
      'replan_needed': '检测到异常，正在重新规划'
    };

    // 处理任务结果
    const tasks = (data.tasks || []).map(task => {
      const resultList = [];
      let statusClass = 'pending';
      let statusIcon = '○';

      if (task.status === 'SUCCESS') {
        statusClass = 'success';
        statusIcon = '✓';
      } else if (task.status === 'RUNNING') {
        statusClass = 'running';
        statusIcon = '◎';
      } else if (task.status === 'FAILED') {
        statusClass = 'failed';
        statusIcon = '✕';
      }

      if (task.result) {
        Object.entries(task.result).forEach(([key, value]) => {
          if (typeof value !== 'object' && key !== 'status') {
            resultList.push({ key: this.formatKey(key), value: String(value) });
          }
        });
      }

      return {
        ...task,
        resultList,
        statusClass,
        statusIcon,
        expanded: false
      };
    });

    // 计算统计信息
    const successCount = tasks.filter(t => t.status === 'SUCCESS').length;
    const pendingCount = tasks.filter(t => t.status !== 'SUCCESS').length;

    // 计算总花费
    let totalCost = 0;
    tasks.forEach(task => {
      if (task.result && task.result.total_price) {
        totalCost += task.result.total_price;
      }
      if (task.result && task.result.price) {
        const price = parseInt(task.result.price.replace(/[^0-9]/g, ''));
        if (!isNaN(price)) totalCost += price;
      }
    });

    // 生成时间线
    const timeline = this.generateTimeline(tasks);

    this.setData({
      status: data.status || 'success',
      statusText: statusTextMap[data.status] || data.status,
      statusDesc: statusDescMap[data.status] || '',
      tasks: tasks,
      notification: data.notification || '',
      totalCount: tasks.length,
      successCount,
      pendingCount,
      totalCost,
      timeline
    });
  },

  // 格式化 key
  formatKey(key) {
    const keyMap = {
      'condition': '天气',
      'temperature': '温度',
      'suggestion': '建议',
      'total': '数量',
      'top_result': '推荐',
      'booking_id': '预订号',
      'restaurant': '餐厅',
      'time': '时间',
      'party_size': '人数',
      'my_number': '排队号',
      'waiting_ahead': '等待桌数',
      'estimated_wait': '预计等待',
      'item': '商品',
      'price': '价格',
      'deliver_time': '送达时间',
      'total_price': '总价'
    };
    return keyMap[key] || key;
  },

  // 生成时间线
  generateTimeline(tasks) {
    const timeline = [];
    const now = new Date();

    tasks.forEach((task, index) => {
      const time = new Date(now.getTime() + index * 2 * 60000);
      const timeStr = `${time.getHours().toString().padStart(2, '0')}:${time.getMinutes().toString().padStart(2, '0')}`;

      let type = 'success';
      if (task.status === 'FAILED') type = 'error';
      if (task.status === 'RUNNING') type = 'warning';

      let text = `${task.name}`;
      if (task.status === 'SUCCESS') {
        text += ' - 执行成功';
      } else if (task.status === 'FAILED') {
        text += ' - 执行失败，已启用备选方案';
      }

      timeline.push({
        time: timeStr,
        text,
        type,
        isLast: index === tasks.length - 1
      });
    });

    return timeline;
  },

  // 切换任务详情展开/收起
  onToggleTask(e) {
    const { index } = e.currentTarget.dataset;
    const key = `tasks[${index}].expanded`;
    this.setData({
      [key]: !this.data.tasks[index].expanded
    });
  },

  // 分享
  onShareAppMessage() {
    return {
      title: '我的美团 AI 行程安排',
      path: '/pages/index/index'
    };
  },

  // 分享按钮点击
  onShare() {
    // 触发分享
  },

  // 返回首页
  onBack() {
    wx.switchTab({
      url: '/pages/index/index'
    });
  }
});
