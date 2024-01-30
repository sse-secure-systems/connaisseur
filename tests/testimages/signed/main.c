#include <unistd.h>
#include <sys/syscall.h>

const char message[] = "Signed.\n";

int main()
{ 
    syscall(SYS_write, STDOUT_FILENO, message, sizeof(message) - 1);
    pause();
    return 0;
}
