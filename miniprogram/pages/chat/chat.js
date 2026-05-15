// pages/chat/chat.js
const api = require('../../utils/api');

Page({
  data: {
    messages: [],
    userInput: '',
    isLoading: false,
    scrollToMessage: '',
    pendingSessionId: null  // 待确认的会话 ID
  },

  onLoad(options) {
    // 如果有初始输入，自动发送
    if (options.input) {
      const input = decodeURIComponent(options.input);
      this.setData({ userInput: input });
      // 延迟一下再发送，让页面先渲染
      setTimeout(() => {
        this.sendMessage(input);
      }, 500);
    }
  },

  // 返回上一页
  onBack() {
    wx.navigateBack();
  },

  // 清空对话
  onClear() {
    wx.showModal({
      title: '提示',
      content: '确定要清空对话记录吗？',
      success: (res) => {
        if (res.confirm) {
          this.setData({ messages: [], pendingSessionId: null });
          wx.showToast({
            title: '已清空',
            icon: 'success'
          });
        }
      }
    });
  },

  // 快速输入
  onQuickInput(e) {
    const { text } = e.currentTarget.dataset;
    this.setData({ userInput: text });
  },

  // 输入事件
  onInput(e) {
    this.setData({
      userInput: e.detail.value
    });
  },

  // 提交事件
  onSubmit() {
    const { userInput, isLoading, pendingSessionId } = this.data;
    if (!userInput || !userInput.trim() || isLoading) {
      return;
    }

    // 有待确认方案时，提示用户先确认或取消
    if (pendingSessionId) {
      wx.showToast({ title: '请先确认或取消当前方案', icon: 'none' });
      return;
    }

    this.sendMessage(userInput);
  },

  // 发送消息
  async sendMessage(content) {
    // 添加用户消息
    const userMessage = {
      id: Date.now(),
      role: 'user',
      type: 'text',
      content: content,
      timeStr: this.formatTime(new Date())
    };

    this.setData({
      messages: [...this.data.messages, userMessage],
      userInput: '',
      isLoading: true,
      scrollToMessage: 'msg-bottom'
    });

    // 添加加载消息
    const loadingMessage = {
      id: Date.now() + 1,
      role: 'assistant',
      type: 'loading',
      content: '正在为你规划行程...'
    };

    this.setData({
      messages: [...this.data.messages, loadingMessage],
      scrollToMessage: 'msg-bottom'
    });

    try {
      // 调用 API
      const result = await api.executeAgent(content);

      // 移除加载消息
      const messages = this.data.messages.filter(m => m.type !== 'loading');

      if (result.status === 'waiting_confirmation') {
        // 方案待确认：显示预览卡片 + 确认按钮
        const planMessage = {
          id: Date.now() + 2,
          role: 'assistant',
          type: 'plan_confirm',
          status: 'waiting_confirmation',
          statusText: '方案已生成',
          summary: result.planSummary || '行程方案已就绪',
          tasks: result.tasks || [],
          route: result.route || null,
          story: result.story || null,
          sessionId: result.sessionId,
          timeStr: this.formatTime(new Date())
        };

        this.setData({
          messages: [...messages, planMessage],
          isLoading: false,
          pendingSessionId: result.sessionId,
          scrollToMessage: 'msg-bottom'
        });
      } else {
        // 直接返回最终结果（非确认流程）
        const planMessage = {
          id: Date.now() + 2,
          role: 'assistant',
          type: 'plan',
          status: result.status,
          statusText: this.getStatusText(result.status),
          summary: `共 ${(result.tasks || []).length} 项任务`,
          tasks: result.tasks || [],
          planId: result.sessionId,
          timeStr: this.formatTime(new Date())
        };

        const notificationMessage = {
          id: Date.now() + 3,
          role: 'assistant',
          type: 'text',
          content: result.notification || '任务执行完成，点击查看详情查看完整行程',
          timeStr: this.formatTime(new Date())
        };

        this.setData({
          messages: [...messages, planMessage, notificationMessage],
          isLoading: false,
          scrollToMessage: 'msg-bottom'
        });
      }

    } catch (err) {
      console.error('请求失败:', err);

      // 移除加载消息，添加错误消息
      const messages = this.data.messages.filter(m => m.type !== 'loading');
      const errorMessage = {
        id: Date.now() + 2,
        role: 'assistant',
        type: 'text',
        content: '抱歉，服务暂时不可用，请稍后重试。',
        timeStr: this.formatTime(new Date())
      };

      this.setData({
        messages: [...messages, errorMessage],
        isLoading: false,
        scrollToMessage: 'msg-bottom'
      });
    }
  },

  // 获取状态文本
  getStatusText(status) {
    const statusMap = {
      'success': '规划完成',
      'partial': '部分完成',
      'error': '执行失败',
      'replan_needed': '重新规划中'
    };
    return statusMap[status] || status;
  },

  // 格式化时间
  formatTime(date) {
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  },

  // 查看行程详情
  onViewPlan(e) {
    const { id } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/plan/plan?id=${id}`
    });
  },

  // 确认方案
  async onConfirmPlan() {
    const { pendingSessionId } = this.data;
    if (!pendingSessionId) return;

    this.setData({ isLoading: true });

    try {
      const result = await api.confirmPlan(pendingSessionId, true);

      // 移除待确认卡片，添加执行结果
      const messages = this.data.messages.filter(m => m.type !== 'plan_confirm');

      const planMessage = {
        id: Date.now(),
        role: 'assistant',
        type: 'plan',
        status: result.status,
        statusText: this.getStatusText(result.status),
        summary: `共 ${(result.tasks || []).length} 项任务`,
        tasks: result.tasks || [],
        planId: pendingSessionId,
        timeStr: this.formatTime(new Date())
      };

      const shareText = result.shareText || '行程已安排好！';
      const notificationMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        type: 'text',
        content: shareText,
        timeStr: this.formatTime(new Date())
      };

      // 缓存行程数据供 plan 页面使用
      const cachedTasks = (result.tasks || []).map(t => {
        const taskResult = (result.results || {})[t.task_id] || {};
        return {
          taskId: t.task_id,
          name: t.name,
          status: t.status || 'SUCCESS',
          result: taskResult
        };
      });
      wx.setStorageSync(`plan_${pendingSessionId}`, {
        status: result.status,
        tasks: cachedTasks,
        notification: shareText
      });

      this.setData({
        messages: [...messages, planMessage, notificationMessage],
        isLoading: false,
        pendingSessionId: null,
        scrollToMessage: 'msg-bottom'
      });

    } catch (err) {
      console.error('确认失败:', err);
      wx.showToast({ title: '确认失败，请重试', icon: 'none' });
      this.setData({ isLoading: false });
    }
  },

  // 取消方案
  async onCancelPlan() {
    const { pendingSessionId } = this.data;
    if (!pendingSessionId) return;

    this.setData({ isLoading: true });

    try {
      await api.confirmPlan(pendingSessionId, false);

      const messages = this.data.messages.filter(m => m.type !== 'plan_confirm');
      const cancelMessage = {
        id: Date.now(),
        role: 'assistant',
        type: 'text',
        content: '好的，已取消本次规划。有需要随时告诉我～',
        timeStr: this.formatTime(new Date())
      };

      this.setData({
        messages: [...messages, cancelMessage],
        pendingSessionId: null,
        isLoading: false,
        scrollToMessage: 'msg-bottom'
      });
    } catch (err) {
      console.error('取消失败:', err);
      // 即使请求失败也清除本地状态
      const messages = this.data.messages.filter(m => m.type !== 'plan_confirm');
      this.setData({
        messages: [...messages, {
          id: Date.now(),
          role: 'assistant',
          type: 'text',
          content: '好的，已取消本次规划。',
          timeStr: this.formatTime(new Date())
        }],
        pendingSessionId: null,
        isLoading: false
      });
    }
  }
});
