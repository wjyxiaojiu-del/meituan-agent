// pages/index/index.js
const api = require('../../utils/api');

Page({
  data: {
    userInput: '',
    quickEntries: [
      {
        icon: '👨‍👩‍👧',
        title: '家庭出游',
        desc: '带孩子和家人周末出游',
        inputs: [
          '这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜'
        ]
      },
      {
        icon: '👫',
        title: '朋友聚会',
        desc: '和朋友一起聚餐娱乐',
        inputs: [
          '周末和4个朋友一起出去玩，2男2女，想找好玩的地方'
        ]
      },
      {
        icon: '💑',
        title: '约会安排',
        desc: '浪漫的二人世界',
        inputs: [
          '想和老婆约会，要有惊喜，吃点好的'
        ]
      },
      {
        icon: '🎉',
        title: '生日派对',
        desc: '庆祝生日的完美安排',
        inputs: [
          '老婆生日，想给她一个惊喜，要有鲜花和蛋糕'
        ]
      }
    ],
    hotItems: [
      {
        emoji: '🎢',
        title: '周末亲子游',
        tag: '热门',
        input: '周末带孩子出去玩，孩子3岁，想找适合幼儿的游乐场'
      },
      {
        emoji: '🍜',
        title: '美食探店',
        tag: '新店',
        input: '想找一家好吃的火锅店，人均100左右'
      },
      {
        emoji: '🎬',
        title: '电影约会',
        tag: '浪漫',
        input: '想和女朋友看电影，然后吃个饭'
      },
      {
        emoji: '🎂',
        title: '生日惊喜',
        tag: '惊喜',
        input: '老婆生日，想给她一个惊喜，要有鲜花和蛋糕'
      }
    ],
    recentPlans: []
  },

  onLoad() {
    // 检查 API 连接
    this.checkApiConnection();
    // 添加入场动画
    this.startAnimation();
  },

  // 入场动画
  startAnimation() {
    // 延迟显示各个模块，营造入场效果
    setTimeout(() => {
      this.setData({ showWelcome: true });
    }, 100);
    setTimeout(() => {
      this.setData({ showQuickEntry: true });
    }, 300);
    setTimeout(() => {
      this.setData({ showHot: true });
    }, 500);
  },

  // 检查 API 连接
  async checkApiConnection() {
    try {
      const res = await api.healthCheck();
      console.log('API 连接正常:', res);
    } catch (err) {
      console.error('API 连接失败:', err);
      wx.showToast({
        title: '服务连接中...',
        icon: 'loading'
      });
    }
  },

  // 输入事件
  onInput(e) {
    this.setData({
      userInput: e.detail.value
    });
  },

  // 提交事件
  onSubmit() {
    const { userInput } = this.data;
    if (!userInput || !userInput.trim()) {
      wx.showToast({
        title: '请输入您的需求',
        icon: 'none'
      });
      return;
    }

    // 跳转到对话页面
    wx.navigateTo({
      url: `/pages/chat/chat?input=${encodeURIComponent(userInput)}`
    });
  },

  // 快捷入口点击
  onQuickEntry(e) {
    const { input } = e.currentTarget.dataset;
    if (input) {
      // 跳转到对话页面
      wx.navigateTo({
        url: `/pages/chat/chat?input=${encodeURIComponent(input)}`
      });
    }
  },

  // 查看行程
  onViewPlan(e) {
    const { id } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/plan/plan?id=${id}`
    });
  }
});
