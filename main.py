import asyncio
import discord
import yt_dlp
import logging
from discord.ext import commands
from mytoken import Token

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# Assume client refers to a discord.Client subclass...
### yt_dlp 구간 ###
# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''
 
 
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}
 
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}
 
ytdlp = yt_dlp.YoutubeDL(ytdl_format_options)
 
 
# 뭔가 데이터 읽어오는 듯?
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
 
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdlp.extract_info(f"ytsearch:{url}", download=False))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
 
        filename = data['url'] if stream else yt_dlp.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

 ### 여기까지 yt_dlp ###
 
# 음악을 재생하는 클래스
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playlist = []
        self.curr = None
   
    @commands.command()
    async def 재생(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""
        async with ctx.typing():
            song = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            self.playlist.append(song)
            await ctx.send(f'"{song.title}"를 목록에 추가했어요.')
            if ctx.voice_client.is_playing() == 0:
                await self.play_next(ctx)

    @commands.command()
    async def 스킵(self, ctx):
        sp = ctx.message.content.split()
        if len(sp)>1 and not sp[1].isdigit():
            await ctx.send("잘못된 명령이에요.")
            return
        if len(sp)==1 or int(sp[1]) == 0:
            ctx.voice_client.stop()
            await ctx.send(f'"{self.curr.title}"를 건너뛰었어요.')
        elif 0 < int(sp[1]) <= len(self.playlist):
            song=self.playlist.pop(int(sp[1])-1)
            await ctx.send(f'"{song.title}"를 삭제했어요.')
        else:
            await ctx.send("잘못된 명령이에요.")
    
    async def play_next(self, ctx):
        if len(self.playlist)>0:
            song = self.playlist.pop(0)
            self.curr = song
            ctx.voice_client.play(song, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            await ctx.send(f'"{song.title}"를 재생 중이에요.')
        else:
            await self.정지(ctx)
         
    @commands.command()
    async def 정지(self, ctx):
        self.playlist = []
        await ctx.voice_client.disconnect()

    @commands.command()
    async def 목록(self, ctx):
        await ctx.send(f"[0]. {self.curr.title}\n"+"\n".join(["{}. {}".format(i+1, self.playlist[i].title) for i in range(len(self.playlist))]))

    @재생.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("음악을 재생하기 위해서, 먼저 음성 채널에 접속해 주세요.")


### 봇 본체 구간 시작 ###
intent = discord.Intents.all()
bot = commands.Bot(command_prefix="!",intents=intent)

@bot.event
async def on_ready():
    print('로그인 중...')
    print(f'{bot.user} 에 로그인 성공!')
    await bot.change_presence(status=discord.Status.online, activity=discord.Game('해체 드래프트'))

@bot.listen('on_message')
async def ogu(message):
    if '오구' in message.content and message.author != bot.user:
        await message.channel.send("{}, 너도 이제 오구야".format(message.author.mention))
 
discord.utils.setup_logging()
async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(Token)

asyncio.run(main())
